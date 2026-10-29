"""Run and record an authenticated concurrent-user load test."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from http.client import HTTPException
from html.parser import HTMLParser
from http.cookiejar import CookieJar
import json
import math
from pathlib import Path
import statistics
import sys
import tempfile
import time
from threading import Barrier, BrokenBarrierError
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlsplit, urlunsplit
from urllib.request import HTTPCookieProcessor, Request, build_opener


MIN_CONCURRENCY = 100
DEFAULT_REPORT_DIRECTORY = Path(__file__).resolve().parent / "results"


@dataclass(frozen=True)
class Credential:
    email: str
    password: str


@dataclass(frozen=True)
class RequestSample:
    worker: int
    request: int
    status: int
    latency_ms: float
    succeeded: bool
    error: str = ""


class CsrfTokenParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.token = None

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "input" and attributes.get("name") == "csrfmiddlewaretoken":
            self.token = attributes.get("value")


def load_credentials(csv_path, required_count):
    """Load unique test accounts from a CSV with email and password columns."""
    credentials = []
    seen_emails = set()
    with Path(csv_path).open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if not reader.fieldnames or not {"email", "password"}.issubset(
            {name.strip().lower() for name in reader.fieldnames}
        ):
            raise ValueError("Credentials CSV must include email and password columns.")

        email_column = next(
            name for name in reader.fieldnames if name.strip().lower() == "email"
        )
        password_column = next(
            name for name in reader.fieldnames if name.strip().lower() == "password"
        )
        for line_number, row in enumerate(reader, start=2):
            email = (row.get(email_column) or "").strip()
            password = row.get(password_column) or ""
            if not email or not password:
                raise ValueError(
                    f"Credentials CSV line {line_number} has a missing email or password."
                )
            normalized_email = email.casefold()
            if normalized_email in seen_emails:
                raise ValueError(f"Credentials CSV contains duplicate email: {email}.")
            seen_emails.add(normalized_email)
            credentials.append(Credential(email=email, password=password))

    if len(credentials) < required_count:
        raise ValueError(
            f"Need at least {required_count} unique test accounts; "
            f"found {len(credentials)}."
        )
    return credentials


def percentile(values, percentile_value):
    ordered = sorted(values)
    index = max(0, math.ceil(percentile_value * len(ordered)) - 1)
    return ordered[index]


def _safe_target_url(url):
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Target URL must be an absolute http:// or https:// URL.")
    if parsed.username or parsed.password:
        raise ValueError("Target URL must not embed credentials.")
    host = f"[{parsed.hostname}]" if ":" in parsed.hostname else parsed.hostname
    if parsed.port:
        host = f"{host}:{parsed.port}"
    return urlunsplit((parsed.scheme, host, parsed.path or "/", parsed.query, ""))


def _redact_target_url(url):
    parsed = urlsplit(url)
    host = f"[{parsed.hostname}]" if ":" in parsed.hostname else parsed.hostname
    if parsed.port:
        host = f"{host}:{parsed.port}"
    return urlunsplit((parsed.scheme, host, parsed.path or "/", "", ""))


def _authenticate(opener, base_url, credential):
    login_url = urljoin(base_url, "/login/")
    with opener.open(login_url, timeout=15) as response:
        parser = CsrfTokenParser()
        parser.feed(response.read().decode("utf-8", errors="replace"))

    if not parser.token:
        raise RuntimeError("Login page did not contain a CSRF token.")

    request = Request(
        login_url,
        data=urlencode(
            {
                "email": credential.email,
                "password": credential.password,
                "csrfmiddlewaretoken": parser.token,
            }
        ).encode(),
        headers={"Referer": login_url},
    )
    with opener.open(request, timeout=15) as response:
        if urlsplit(response.geturl()).path.rstrip("/") == "/login":
            raise RuntimeError("Authentication failed for a test account.")
        response.read()


def _verify_authenticated_access(opener, target_url):
    request = Request(target_url, headers={"X-Load-Test-Probe": "preflight"})
    with opener.open(request, timeout=15) as response:
        requested_path = urlsplit(target_url).path.rstrip("/") or "/"
        final_path = urlsplit(response.geturl()).path.rstrip("/") or "/"
        if final_path != requested_path:
            raise RuntimeError(
                f"Authenticated access redirected to {final_path}; "
                "check the test credentials and target URL."
            )
        if not 200 <= response.status < 400:
            raise RuntimeError(
                f"Authenticated access returned HTTP {response.status}."
            )
        response.read()


def _run_client(worker, credential, request_count, target_url, barrier):
    opener = build_opener(HTTPCookieProcessor(CookieJar()))
    authenticated = False
    requested_path = urlsplit(target_url).path.rstrip("/") or "/"
    try:
        _authenticate(opener, target_url, credential)
        _verify_authenticated_access(opener, target_url)
        authenticated = True
        barrier.wait(timeout=45)
    except (
        HTTPError,
        URLError,
        HTTPException,
        TimeoutError,
        OSError,
        RuntimeError,
        BrokenBarrierError,
    ) as exc:
        barrier.abort()
        return (
            authenticated,
            [],
            f"client {worker} setup failed: {type(exc).__name__}: {exc}",
        )

    samples = []
    for request_number in range(1, request_count + 1):
        started = time.perf_counter()
        request = Request(target_url, headers={"Connection": "keep-alive"})
        try:
            with opener.open(request, timeout=30) as response:
                response.read()
                latency_ms = (time.perf_counter() - started) * 1000
                status = response.status
                response_path = urlsplit(response.geturl()).path.rstrip("/") or "/"
                success = (
                    200 <= status < 400 and response_path == requested_path
                )
                if response_path != requested_path:
                    error = f"redirected to {response_path}"
                else:
                    error = "" if success else f"HTTP {status}"
        except (HTTPError, URLError, HTTPException, TimeoutError, OSError) as exc:
            latency_ms = (time.perf_counter() - started) * 1000
            status = exc.code if isinstance(exc, HTTPError) else 0
            success = False
            error = f"{type(exc).__name__}: {exc}"

        samples.append(
            RequestSample(
                worker=worker,
                request=request_number,
                status=status,
                latency_ms=latency_ms,
                succeeded=success,
                error=error,
            )
        )
    return True, samples, ""


def _write_report(report, report_path):
    report_path = Path(report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            newline="\n",
            dir=report_path.parent,
            prefix=f".{report_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as file:
            temporary_path = Path(file.name)
            json.dump(report, file, indent=2)
            file.write("\n")
        temporary_path.replace(report_path)
    except OSError:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise


def run_load_test(
    target_url,
    credentials,
    request_count,
    concurrency,
    threshold_seconds,
    report_path,
    report_metadata=None,
):
    if concurrency < MIN_CONCURRENCY:
        raise ValueError(f"Concurrency must be at least {MIN_CONCURRENCY}.")
    if len(credentials) < concurrency:
        raise ValueError("Provide at least one unique credential per concurrent client.")
    if request_count < concurrency:
        raise ValueError("Total requests must be at least the concurrency.")
    if threshold_seconds <= 0:
        raise ValueError("Latency threshold must be greater than zero.")

    safe_url = _safe_target_url(target_url)
    measurement_start = {}

    def mark_measurement_start():
        measurement_start["monotonic"] = time.perf_counter()
        measurement_start["utc"] = datetime.now(timezone.utc).isoformat()

    barrier = Barrier(concurrency, action=mark_measurement_start)
    request_counts = [
        request_count // concurrency
        + (1 if worker < request_count % concurrency else 0)
        for worker in range(concurrency)
    ]
    run_started_at = datetime.now(timezone.utc).isoformat()
    client_results = []
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [
            executor.submit(
                _run_client,
                worker,
                credentials[worker],
                request_counts[worker],
                safe_url,
                barrier,
            )
            for worker in range(concurrency)
        ]
        for future in futures:
            try:
                client_results.append(future.result())
            except (
                HTTPError,
                URLError,
                HTTPException,
                TimeoutError,
                OSError,
                RuntimeError,
            ) as exc:
                client_results.append((False, [], f"client worker failed: {exc}"))
    elapsed_seconds = (
        time.perf_counter() - measurement_start["monotonic"]
        if "monotonic" in measurement_start
        else 0
    )

    authenticated_clients = sum(1 for authenticated, _, _ in client_results if authenticated)
    samples = [sample for _, worker_samples, _ in client_results for sample in worker_samples]
    errors = [error for _, _, error in client_results if error]
    successful_samples = [sample for sample in samples if sample.succeeded]
    failed_samples = [sample for sample in samples if not sample.succeeded]
    latencies = [sample.latency_ms for sample in samples]
    p95_ms = percentile(latencies, 0.95) if latencies else None
    max_ms = max(latencies) if latencies else None
    threshold_ms = threshold_seconds * 1000
    slow_count = sum(sample.latency_ms >= threshold_ms for sample in samples)
    passed = (
        authenticated_clients >= MIN_CONCURRENCY
        and authenticated_clients == concurrency
        and len(samples) == request_count
        and not failed_samples
        and not errors
        and slow_count == 0
    )

    report = {
        "requirement": "NFR-02",
        "started_at_utc": run_started_at,
        "measurement_started_at_utc": measurement_start.get("utc"),
        "target": _redact_target_url(safe_url),
        "configured_concurrency": concurrency,
        "minimum_required_concurrency": MIN_CONCURRENCY,
        "authenticated_clients": authenticated_clients,
        "requested_requests": request_count,
        "completed_requests": len(samples),
        "successful_requests": len(successful_samples),
        "failed_requests": len(failed_samples),
        "client_setup_errors": errors,
        "elapsed_seconds": round(elapsed_seconds, 4),
        "throughput_requests_per_second": round(
            len(samples) / elapsed_seconds if elapsed_seconds else 0, 2
        ),
        "latency_ms": {
            "median": round(statistics.median(latencies), 2) if latencies else None,
            "p95": round(p95_ms, 2) if p95_ms is not None else None,
            "max": round(max_ms, 2) if max_ms is not None else None,
            "threshold": threshold_ms,
        },
        "slow_requests": slow_count,
        "status_counts": {
            str(status): sum(sample.status == status for sample in samples)
            for status in sorted({sample.status for sample in samples})
        },
        "failures": [
            asdict(sample)
            for sample in failed_samples
        ],
        "slow_request_details": [
            asdict(sample)
            for sample in samples
            if sample.latency_ms >= threshold_ms
        ],
        "passed": passed,
    }
    if report_metadata is not None:
        report["environment"] = report_metadata
    _write_report(report, report_path)
    return report


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Evaluate 100+ distinct authenticated users concurrently."
    )
    parser.add_argument("--url", required=True, help="Protected endpoint URL to test.")
    parser.add_argument(
        "--users-file",
        required=True,
        help="CSV file with unique email,password columns for test accounts.",
    )
    parser.add_argument("--requests", type=int, default=1000)
    parser.add_argument("--concurrency", type=int, default=100)
    parser.add_argument("--threshold", type=float, default=3.0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.concurrency < MIN_CONCURRENCY:
        parser.error(f"--concurrency must be at least {MIN_CONCURRENCY}.")
    if args.requests < args.concurrency:
        parser.error("--requests must be at least --concurrency.")
    if args.threshold <= 0:
        parser.error("--threshold must be greater than zero.")
    return args


def main(argv=None):
    args = parse_args(argv)
    default_filename = f"nfr02-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.json"
    report_path = args.output or DEFAULT_REPORT_DIRECTORY / default_filename

    try:
        if Path(args.users_file).resolve() == report_path.resolve():
            raise ValueError("The report output path must not overwrite the users file.")
        credentials = load_credentials(args.users_file, args.concurrency)
        report = run_load_test(
            target_url=args.url,
            credentials=credentials,
            request_count=args.requests,
            concurrency=args.concurrency,
            threshold_seconds=args.threshold,
            report_path=report_path,
        )
    except (OSError, ValueError) as exc:
        print(f"Load test could not run: {exc}", file=sys.stderr)
        return 2

    print(
        f"NFR-02 {'PASS' if report['passed'] else 'FAIL'}: "
        f"{report['authenticated_clients']}/{report['configured_concurrency']} "
        f"authenticated users; "
        f"{report['successful_requests']}/{report['requested_requests']} "
        f"requests succeeded; {report['failed_requests']} failures; "
        f"{report['slow_requests']} slow requests."
    )
    print(
        "Latency (ms): "
        f"median={report['latency_ms']['median']}, "
        f"p95={report['latency_ms']['p95']}, "
        f"max={report['latency_ms']['max']}; "
        f"throughput={report['throughput_requests_per_second']} req/s"
    )
    print(f"Results saved to: {report_path}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
