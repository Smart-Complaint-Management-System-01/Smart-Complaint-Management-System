# Test Execution and Quality Assurance Report

**Project:** Smart Complaint Management System  
**Assessment date:** 15 November 2026 (Asia/Kolkata)  
**Branch:** `feature/part3-testing-qa`  
**Base:** latest `main`, commit `b067bf3` (PR #52, FR-12 notifications)  
**Scope:** Sprint 1 and Sprint 2 regression testing and QA evidence

## Summary

The QA branch now includes all changes present in the fetched main branch, including FR-07 complaint updates, FR-09 assignment, FR-12 notifications, and NFR-02’s concurrency test. That integration check found three URL routes whose view handlers were absent from the merged main code. The QA branch restores those handlers from the corresponding feature implementations and adds FR-07 service and route regression coverage. These changes are local to this feature branch.

The focused FR-07 suite passed **11/11 tests**. Django’s system check passed, and `makemigrations --check --dry-run` reported no model changes. The integrated suite discovered 250 tests; its run produced one failure and one error in the 100-user concurrency test when SQLite was used. Concurrent requests triggered SQLite connection/transaction errors. The run therefore does not establish a full-suite pass on SQLite or validate the target MySQL backend.

A committed NFR-02 result from 29 October 2026 records a separate MySQL run with 100 authenticated clients, 100 successful HTTP 200 responses, zero failures, 2.4237 seconds elapsed, and 2,393.20 ms p95 latency under the test’s 30-second limit. This is existing evidence, not a rerun of the current branch. MySQL was unavailable for the current execution.

## Execution record

| Check | Result | Evidence / limitation |
|---|---|---|
| Integrated Django suite with temporary in-memory SQLite | 250 tests discovered; 248 passed, with one test reporting a failure and an error | Both outcomes are from `accounts.tests.test_authenticated_concurrency.AuthenticatedConcurrencyTests.test_100_distinct_authenticated_users_can_request_protected_page`; concurrent SQLite requests raise connection/transaction errors. Not a clean full-suite pass. |
| Focused assignment and notification suites | Pass: 38/38 | `complaints.tests.test_assignment` and `complaints.tests.test_notifications`. |
| Focused complaint-update suite | Pass: 11/11 | `complaints.tests.test_complaint_update`; verifies service behavior, owner/admin routes, authorization, validation, and resolved-complaint rejection. |
| Django system check | Pass | `System check identified no issues (0 silenced).` |
| Migration drift check | Pass | `makemigrations --check --dry-run` reported `No changes detected`. |
| NFR-02 MySQL load evidence | Pass: 100/100 HTTP 200, 0 failures | Existing `loadtests/results/nfr02-100-users.json` and `.csv`; run 29-Oct-2026, MySQL, Django threaded server, p95 2,393.20 ms, 30,000 ms threshold. |
| Current MySQL test-suite rerun | Not run | MySQL80 service was stopped and unavailable at `127.0.0.1:3306`; service start was blocked by Windows service-control permissions. |

The Django suite used temporary in-process SQLite settings; committed database settings and application environment files were not changed. The current SQLite concurrency result is backend-specific and should not be interpreted as a MySQL failure. A current MySQL rerun remains necessary to validate the integrated branch against its configured database.

## Requirement coverage

### Functional requirements

| Requirement | Automated evidence | Status |
|---|---|---|
| FR-01 Registration | `accounts.tests.test_forms` | Covered |
| FR-02 Authentication | `accounts.tests.test_authentication`, `test_logout`, `test_auth_security` | Covered |
| FR-03 Role-based access | `accounts.tests.test_roles`, `complaints.tests.test_authorization` | Covered |
| FR-04 Complaint submission and ID | `complaints.tests.test_submission`, `test_validation_feedback`, `test_error_recovery` | Covered |
| FR-05 Complaint status viewing | `complaints.tests.test_complaint_status`, `test_history` | Covered |
| FR-06 History | `complaints.tests.test_history` | Covered |
| FR-07 Complaint updates | `complaints.tests.test_complaint_update` (3 service tests and 8 route tests) | Covered; focused suite passes |
| FR-08 Admin complaint management | `complaints.tests.test_admin_management`, `test_authorization` | Covered |
| FR-09 Assignment | `complaints.tests.test_assignment` | Covered |
| FR-10 Resolution | `complaints.tests.test_resolution` | Covered |
| FR-11 Search and filtering | `complaints.tests.test_search` | Covered |
| FR-12 Notifications | `complaints.tests.test_notifications` | Covered by workflow, recipient, authorization, read-state, and pagination tests |

### Non-functional requirements

| Requirement | Automated evidence | Status |
|---|---|---|
| NFR-01 Response time | `test_performance` checks response-time headers, slow-request logging, and pagination | Partial; no current representative request timing against the 3-second target |
| NFR-02 Concurrent users | Committed MySQL load result plus current SQLite concurrency test | Prior MySQL run passed 100/100; current SQLite run failed due SQLite concurrent connection/transaction errors. Repeat against current branch on MySQL. |
| NFR-03 Persistence | `test_persistence` verifies database round trips inside the test database | Partial; no current MySQL stop/restart persistence check |
| NFR-04 Error recovery | `test_error_recovery` simulates save failures and submission-token replay | Covered by automated tests |
| NFR-05 Usability | `test_usability` checks required-field labels, messaging, and form controls | Partial; no representative-user evaluation |
| NFR-06 Validation feedback | `test_validation_feedback`, `accounts.tests.test_forms` | Covered by automated tests |
| NFR-07 Authentication security | `accounts.tests.test_auth_security` | Covered by automated tests |
| NFR-08 Authorization | `complaints.tests.test_authorization`, assignment/resolution authorization tests | Covered by automated tests |
| NFR-09 Password protection | `accounts.tests.test_password_security` | Covered by automated tests |
| NFR-10 Session security | `accounts.tests.test_logout`, `test_auth_security` | Covered by automated tests |

## Integration finding and follow-up

The integrated `complaints/urls.py` referenced `admin_add_update`, `add_info`, and `admin_assign`, but those handlers were missing from merged `complaints/views.py`. This prevented URL loading on the updated main baseline. The QA branch restores the FR-07 and FR-09 handlers and adds regression tests for the previously missing FR-07 routes. The FR-09 assignment feature already has its own assignment test suite.

Remaining QA work is to rerun all tests and the concurrency scenario against the current branch on MySQL, perform representative response-time and usability checks, and validate persistence across an application restart. No commit, push, pull request, merge, or collaborator change has been made.

## Artifacts

- `Docs/Test_Plan_Draft.docx` — version 1.2, updated FR-07 cases and traceability against integrated `main`.
- `Docs/Test_Execution_Report_2026-11-15.md` — current test results, branch baseline, evidence, and limitations.
- `loadtests/results/nfr02-100-users.json` and `.csv` — existing NFR-02 MySQL run evidence from 29-Oct-2026.
