# NEC Engineering Analysis SaaS — Full System Audit

**Date:** 2025-02-04  
**Scope:** Frontend + Backend — Authentication, Settings, Validation API, Submission Comparison, Report Generation, Data Retention, Security.

---

## 1. AUTHENTICATION & SESSION ARCHITECTURE

### Backend

| Item | Implementation |
|------|----------------|
| **Method** | JWT (Bearer token), not session cookies |
| **Token creation** | `app/auth.py`: `create_access_token(user_id)` — payload `{"sub": str(user_id), "exp": expire}`; signed with `settings.JWT_SECRET_KEY`, algorithm `settings.JWT_ALGORITHM` (HS256). |
| **Expiry** | `config.py`: `ACCESS_TOKEN_EXPIRE_DAYS = 7` |
| **Endpoints** | `POST /api/auth/signup`, `POST /api/auth/login`, `GET /api/auth/me`, `PATCH /api/auth/me`. No explicit logout endpoint (stateless JWT; client discards token). |
| **Password hashing** | `app/auth.py`: bcrypt via `hash_password()` / `verify_password()` (72-byte limit respected). |
| **Token verification** | `app/routers/auth.py`: `get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db)` — uses `HTTPBearer(auto_error=False)`, `decode_access_token(credentials.credentials)`, then `get_user_by_id(db, user_id)`. Returns 401 for missing/invalid/expired token or user not found. |

### Frontend

| Item | Implementation |
|------|----------------|
| **AuthContext** | `context/AuthContext.jsx`: `user` and `loading` state; on mount runs `getAuthToken()` from localStorage, then `apiGetMe()`; sets user from response or clears token on failure. Exposes `login`, `signup`, `logout`, `updateProfile`, `isAuthenticated: !!user`. |
| **Token storage** | `services/api.js`: `AUTH_TOKEN_KEY = 'nec_analysis_token'` — stored in **localStorage** via `setAuthToken` / `getAuthToken`. |
| **ProtectedRoute** | `components/ProtectedRoute.jsx`: uses `useAuth().isAuthenticated`; if false, redirects to `/login` with `state={{ from: location.pathname }}`. Does **not** consider `loading`. |

### Auth flow (text diagram)

```
[Client]                    [Backend]
   |                             |
   |  POST /api/auth/signup      |
   |  or POST /api/auth/login   |
   |--------------------------->|
   |  { access_token, user }    |
   |<---------------------------|
   |  setAuthToken(token)       |
   |  setUser(user)             |
   |                             |
   |  GET /api/auth/me           |
   |  Authorization: Bearer ...  |
   |--------------------------->|
   |  200 { user }              |
   |<---------------------------|
   |  (any protected request    |
   |   sends Bearer token)      |
   |                             |
   |  Logout: setAuthToken(null) |
   |  setUser(null)             |
```

### Root cause of “refresh logs user out but header still shows name”

1. On full page refresh, `AuthProvider` mounts with `user = null`, `loading = true`.
2. `ProtectedRoute` uses `isAuthenticated === !!user` → **false** while user is null.
3. So the app **immediately** redirects to `/login` (it does not wait for `loading` to finish).
4. Then `apiGetMe()` completes and **sets** `user` in context. So the user ends up on the **login page** with **user state populated** — hence the header (which reads `user.name` from context) still shows the name.

**Required fixes**

- **ProtectedRoute:** Treat “loading” as “unknown auth state”. While `loading === true`, render a loading spinner (or blank) and do **not** redirect. Only when `loading === false`: if `!isAuthenticated` redirect to login.
- Optionally: clear token and user on 401 from any API call (e.g. in api.js interceptor) so expired tokens don’t leave stale user in context.

---

## 2. USER SETTINGS INTEGRATION

### Backend

- **Model:** `app/models/user.py` — `User`: `timezone`, `report_naming_preference`, `data_retention_days`, `organisation_logo_url`, `preferences` (JSONB). Defaults in `DEFAULT_PREFERENCES` (presentation/workflow only; see model docstring).
- **Endpoints:** `GET /api/auth/me`, `PATCH /api/auth/me` — read/update all of the above.

### Do settings influence validate_programme / report generation / planner guidance?

- **validate_programme:** No. Validation does not read the current user or user settings.
- **Report generation:** No. `POST /api/v1/generate_report` accepts only `json_file` and `format`; it does not receive user id, report_naming_preference, or confidentiality_mode. Filename is server-side timestamp only.
- **Planner guidance:** Built inside validation from contract + submission stage + planner assumptions; no user settings.

### Frontend

- **Stored:** AccountSettings syncs from `user` (from `/me`) into local state and sends updates via `PATCH /api/auth/me` (profile, reportNamingPreference, dataRetentionDays, preferences). So settings **are persisted** in the backend.
- **Used:**  
  - **report_naming_preference:** Used only on the frontend in ResultsReport for the **download** filename (`getReportFilename()`).  
  - **default_report_format, confidentiality_mode, etc.:** Stored and sent to backend on PATCH, but **no backend logic** uses them (e.g. report generator does not receive format preference or confidentiality; format is chosen per request in the generate-report call).

### Table: Setting → Persisted → Used → Effective

| Setting | Persisted | Used (where) | Effective |
|--------|-----------|---------------|-----------|
| name, organisation, role, timezone | Yes (PATCH /me) | Profile display, report context | Cosmetic / display |
| report_naming_preference | Yes | ResultsReport download filename | **Frontend only** (filename) |
| data_retention_days | Yes | Stored on user | **Not enforced** (no pruning job) |
| organisation_logo_url | Yes | Can be shown in UI | Cosmetic |
| preferences (e.g. default_report_format, confidentiality_mode, programme_stage_assumption) | Yes | Partially (e.g. stage in validation flow) | **Mostly cosmetic**; validation uses submission_stage from form, not user preference; report does not use confidentiality or default format from user |

### Missing integrations

- Report generation does not receive: user id, report_naming_preference, confidentiality_mode, or default_report_format. Naming is client-side only; server uses a fixed timestamp pattern.
- data_retention_days is not used by any pruning job or retention policy.
- default_report_format is not used when calling generate report (user must choose format per action).

---

## 3. VALIDATION API CONTRACT ALIGNMENT

### Backend response schema (key top-level fields from validate_programme)

- `contract_summary`, `programme_summary`, `alignment` (with `scope_coverage`, `programme_compliance_model`, etc.)
- `validation_summary`: `acceptability_status`, `overall_status`, `programme_decision_text`, `programme_decision_detail`, `acceptability_failure_reasons` (list), `quality_summary`, `summary_explanation`, etc.
- `obligations_report`, `obligations_not_represented_but_mandatory`, `scope_evidence_table`
- `obligation_readiness`, `submission_stage`
- `recommendations`: list of objects (e.g. `{ "text": "...", "priority": "high" }` or similar)
- `submission_comparison`: `null` or `{ "comparison_mode", "previous_programme_name", "status_change", "became_aligned", "became_unaligned" }`
- `metadata`, `response_signature`

### Frontend consumption

- **validationSummary.js:** `buildValidationPreview` / `buildResultsForReport` read `validation_summary`, `alignment`, `contract_summary`, `programme_summary`.  
  - `failureReasons` = `vs.acceptability_failure_reasons` (array).  
  - `requiredActions` = `validationResult.recommendations` (array).
- **ResultsReport.jsx:** Renders `reportContent.failureReasons` and `reportContent.requiredActions`. For each item: `typeof r === 'string' ? r : r.reason || r.text || ''` and `action?.text || action?.message || String(action)`.

### Mismatch / [object Object] cause

- Backend `recommendations` and sometimes `acceptability_failure_reasons` can contain **objects** (e.g. `{ "text": "...", "priority": "..." }`). If the frontend sees an object without `text`, `message`, or `reason`, it falls back to `String(action)` → **"[object Object]"**.
- **Fix:** Normalise in `validationSummary.js` and in the component: for each item, if object use `item?.text ?? item?.message ?? item?.reason ?? (typeof item === 'string' ? item : null)` and if still null/undefined use a safe fallback (e.g. "—") instead of `String(item)`.

### Summary

- **Backend schema:** As above; `recommendations` and failure reasons are structured.
- **Frontend expected:** Same top-level keys; display assumes string or object with `text`/`message`/`reason`.
- **Mismatch:** Object items without those keys render as "[object Object]". Safe extraction in one place (utility + component) resolves it.

---

## 4. SUBMISSION COMPARISON FEATURE

### Backend

- **previous_xer_file:** Optional `UploadFile` on `POST /api/v1/validate_programme`. Validated as .xer, size limit same as main XER. Read into `previous_xer_content` and used only for comparison.
- **submission_comparison:** When `previous_xer_content` is present, backend runs validation for the previous XER, then `build_submission_evolution(current, previous)` and sets `output_dict["submission_comparison"] = { "comparison_mode": "file_upload", "previous_programme_name", "status_change", "became_aligned", "became_unaligned" }`. Otherwise `submission_comparison` is `null`.

### Frontend

- **Previous file upload:** **Not present.** `ProgrammeValidation.jsx` and `api.js` `validateProgramme(xerFile, contractAnalysisJson)` send only one XER (`xer_file`) and optional `json_file`. No `previous_xer_file` is sent.
- **Comparison results:** No UI reads `validationResult.submission_comparison`. ProgrammeCompare page compares two programmes by running validation **twice** (two separate XERs) and comparing the two results client-side; it does not use the backend’s single-request “previous + current” comparison.

### Feature completeness

- **Backend:** Complete (previous_xer_file accepted, submission_comparison returned).
- **Frontend:** **Incomplete** — no upload for “previous programme”, no display of `submission_comparison` (status_change, became_aligned, became_unaligned).

### Missing UI wiring

- Add optional “Previous programme (XER)” file input on the programme step (or a dedicated “compare with previous” mode).
- Extend `validateProgramme` to send `previousXerFile` when provided.
- On results/review, if `validationResult.submission_comparison` is present, render status_change and obligation deltas (became_aligned / became_unaligned).

---

## 5. REPORT GENERATION INTEGRATION

### Backend

- **Endpoint:** `POST /api/v1/generate_report` — body: multipart with `json_file` (validation JSON), query `format=pdf|docx|html`. Saves under `runtime/reports` with name like `report_{timestamp}.pdf` and returns file. No user id, no naming preference, no confidentiality mode in the request.

### Frontend

- **Reporting preferences:** User can set default_report_format and confidentiality_mode in AccountSettings; they are saved to user preferences via PATCH /me but **are not sent** to generate_report.
- **Report format:** User chooses format at download time in ResultsReport (e.g. PDF); `generateReport(validationResult, 'pdf')` is called with that format. So format selection works per request; default_report_format is not applied automatically.
- **Naming:** Download filename is set client-side from `user.reportNamingPreference` in ResultsReport (`getReportFilename()`). Backend response filename is server-generated and can differ.

### Disconnected report features

- **Confidentiality mode:** Stored in user preferences but not sent to backend; report generator does not redact or label “confidential”.
- **Report naming preference:** Only affects client-side download filename; backend does not use it.
- **Default report format:** Not used when calling generate report; user must select format each time (or frontend could prefill from preference).
- **User/org for report header/footer:** Not passed to backend; report content does not include current user or organisation from settings.

---

## 6. DATA RETENTION

### Backend

- **Setting:** `User.data_retention_days` (default 365), persisted via PATCH /me.
- **Enforcement:** **None.** No scheduled job or endpoint prunes analysis runs, validation reports, or other user data by retention days. No code path reads `data_retention_days` for deletion.

### Frontend

- **Setting:** Data & privacy tab in AccountSettings; user can set retention days; value is saved to backend. No other frontend behaviour (e.g. “delete after N days”) is implemented.

### Compliance gaps

- **Gap:** Retention setting is stored but not enforced. To be compliant with a “retain for X days” policy, backend (or a job) must delete or anonymise user data older than `user.data_retention_days` (e.g. analysis runs, saved validation outputs). Frontend cannot enforce this alone.

---

## 7. SECURITY REVIEW

- **JWT storage:** Token in **localStorage** — vulnerable to XSS; if an attacker can run JS, they can read the token. Prefer httpOnly cookies for refresh/store and short-lived tokens, or ensure strict CSP and no unsanitised user content to minimise XSS.
- **CSRF:** No CSRF tokens; API is Bearer-based and not cookie-based for auth, so classic form CSRF is less relevant. State-changing operations require the JWT.
- **Rate limiting:** Applied to **all** `/api/` routes in `SecurityMiddleware` (per-IP, file-based under `runtime/rate_limit`). Auth endpoints (login/signup) are **not** exempt, so they are rate-limited — good.
- **Password reset:** ForgotPassword page exists in frontend; no backend endpoint found for reset (no tokenised reset link or email). So “forgot password” is currently non-functional on the backend.
- **File upload validation:** XER and JSON validated (extension, size, content) in validate_programme; analyze_contract validates file type/size. Consistent use of security_config limits (e.g. MAX_XER_FILE_SIZE_BYTES).

### Diagrams (text)

**System architecture**

```
[Browser] ---> [FastAPI] ---> [PostgreSQL]
    |              |
    |              +---> [runtime/] (reports, analysis, validation, rate_limit, audit)
    |              +---> OpenAI/Azure (if AI_MODE real/azure)
    |
    +-- localStorage(nec_analysis_token)
    +-- AuthContext(user, loading)
```

**Auth flow**

```
Login/Signup --> JWT created --> Stored in localStorage
     |
     v
Every /api/* request --> Authorization: Bearer <token>
     |
     v
get_current_user (where used) --> decode_access_token --> get_user_by_id --> 401 or User
```

**Validation flow**

```
Contract (PDF) --> analyze_contract --> analysis JSON
     |
     v
XER + optional previous_xer + optional json_file --> validate_programme
     |
     v
validation JSON --> generate_report (format) --> PDF/DOCX/HTML
     |
     v
build_validation_report (same structure) --> Frontend preview
```

### Issue summary

- **Critical production blockers:**  
  - Login required before use but **refresh sends user to login** (ProtectedRoute doesn’t wait for loading).  
  - **Email verification not implemented** — anyone with a valid email can sign up and log in.  
  - **Data retention not enforced** — compliance risk.

- **Medium:**  
  - [object Object] in report/review (recommendations/failure reasons shape).  
  - JWT in localStorage (XSS risk).  
  - Report generation ignores user preferences (naming, confidentiality, default format).  
  - Submission comparison not wired in UI (no previous XER upload, no display of submission_comparison).  
  - Password reset not implemented.

- **Cosmetic / low:**  
  - Default report format not pre-filled from user preference.  
  - Some preferences stored but only partially used.

### Recommended fix order

1. **Auth UX:** Fix ProtectedRoute loading so refresh doesn’t incorrectly redirect; then implement email verification (Phase 2).
2. **Email verification:** Implement SMTP verification and block login until verified (Phase 2).
3. **Display bugs:** Normalise recommendation/failure-reason display to prevent [object Object].
4. **Report:** Pass user preferences (naming, format, confidentiality) to report endpoint or document that naming is client-only and add server-side naming/confidentiality later.
5. **Retention:** Implement a pruning job or scheduled task that deletes/anonymises data older than `user.data_retention_days`.
6. **Submission comparison:** Add previous XER upload and display of submission_comparison.
7. **Security:** Consider moving token to httpOnly cookie or shortening token lifetime and adding refresh flow; implement password reset.

---

## Phase 2 — Email verification (SMTP) — implementation status

- **Backend (already in place):**  
  - User model: `is_verified`, `email_verification_token`, `email_verification_expires`.  
  - Migration: `backend/migrations/add_email_verification_columns.sql`.  
  - Signup: ZeroBounce (if configured), create user with `is_verified=False`, generate token (`secrets.token_urlsafe`), send email via `app/services/smtp_email.send_verification_email` (SMTP from env: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM`).  
  - Login: returns 403 with `error_code: "EMAIL_NOT_VERIFIED"` when `is_verified=False`.  
  - `GET /api/auth/verify-email?token=...`: single-use, sets `is_verified=True`, clears token/expiry.  
  - `POST /api/auth/resend-verification`: body `{ email }`, rate-limited via SecurityMiddleware.

- **Frontend (wired):**  
  - **Signup:** On success, API returns `{ message, email }` (no token); user is redirected to Login with `state.signupMessage` ("Check your email to verify…").  
  - **Login:** On 403 with `EMAIL_NOT_VERIFIED`, shows "Please verify your email before logging in" and a "resend verification email" button; `apiResendVerification(email)` calls resend endpoint.  
  - **VerifyEmail page:** Route `/verify-email`, reads `token` from query, calls `apiVerifyEmail(token)`, shows success or expired/invalid message and link to sign in.  
  - **api.js:** `apiSignup` handles `{ message, email }`; `apiLogin` attaches `errorCode: 'EMAIL_NOT_VERIFIED'` on 403; `apiVerifyEmail`, `apiResendVerification` added.  
  - **AuthContext:** `signup` supports both legacy `{ access_token, user }` and new `{ message, email }` response.

- **Remaining (optional):**  
  - Ensure `FRONTEND_BASE_URL` and SMTP env vars are set in production so verification links and emails work.  
  - Add rate limit specifically for resend-verification if desired (currently covered by global API rate limit).

---

*End of Phase 1 — System Audit; Phase 2 — Email verification implemented and frontend aligned.*
