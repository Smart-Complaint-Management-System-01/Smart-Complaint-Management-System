"""Run the full test suite and generate the Sprint testing reports.

Usage (from the repo root, with the venv active):
    pip install -r requirements-dev.txt
    python generate_test_reports.py

Outputs (Docs/reports/):
    unit_test_report.html      - Unit Test Report (every test, pass/fail, duration)
    junit_results.xml          - machine-readable test results
    coverage_html/index.html   - Code + Branch Coverage (line-by-line, partial branches in yellow)
    coverage_summary.txt       - per-file statement and branch coverage table
    coverage.json              - raw numbers used for the summaries below
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "Docs" / "reports"


def run(*args):
    print("$", " ".join(args))
    return subprocess.run([sys.executable, "-m", *args], cwd=ROOT).returncode


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (ROOT / ".coverage").unlink(missing_ok=True)

    test_rc = run(
        "coverage", "run", "-m", "pytest", "-v",
        f"--html={OUT / 'unit_test_report.html'}", "--self-contained-html",
        f"--junitxml={OUT / 'junit_results.xml'}",
    )

    with open(OUT / "coverage_summary.txt", "w", encoding="utf-8") as fh:
        subprocess.run([sys.executable, "-m", "coverage", "report"], cwd=ROOT, stdout=fh)
    run("coverage", "html")
    run("coverage", "json", "-o", str(OUT / "coverage.json"))

    totals = json.loads((OUT / "coverage.json").read_text())["totals"]
    stmt = 100 * totals["covered_lines"] / max(totals["num_statements"], 1)
    branch = 100 * totals["covered_branches"] / max(totals["num_branches"], 1)
    print()
    print(f"Statement coverage : {totals['covered_lines']}/{totals['num_statements']} = {stmt:.2f}%")
    print(f"Branch coverage    : {totals['covered_branches']}/{totals['num_branches']} = {branch:.2f}%")
    print(f"Combined (coverage.py) : {totals['percent_covered']:.2f}%")
    print(f"Reports written to {OUT}")
    sys.exit(test_rc)


if __name__ == "__main__":
    main()
