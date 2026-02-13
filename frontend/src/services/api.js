/**
 * API service for NEC Engineering Analysis.
 * All backend calls go through here. User-facing error messages only.
 */

const API_BASE = process.env.REACT_APP_API_URL || 'http://127.0.0.1:8000';

const AUTH_TOKEN_KEY = 'nec_analysis_token';

let _onUnauthorized = () => {};

export function setUnauthorizedHandler(fn) {
  _onUnauthorized = typeof fn === 'function' ? fn : () => {};
}

export function getAuthToken() {
  try {
    return localStorage.getItem(AUTH_TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setAuthToken(token) {
  try {
    if (token) localStorage.setItem(AUTH_TOKEN_KEY, token);
    else localStorage.removeItem(AUTH_TOKEN_KEY);
  } catch (_) {}
}

function authHeaders() {
  const token = getAuthToken();
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

/** Check response for 401 and trigger logout + redirect. Returns true if 401 was handled. */
function checkUnauthorized(response) {
  if (response && response.status === 401) {
    _onUnauthorized();
    return true;
  }
  return false;
}

/**
 * Parse backend structured error { error_code, error_message, details }.
 * Returns user-facing message string. Never returns raw JSON.
 */
export function parseStructuredError(data) {
  if (!data || typeof data !== 'object') return null;
  const msg = data.error_message || data.detail;
  if (typeof msg === 'string' && msg.trim()) return msg.trim();
  if (typeof data.detail === 'string') return data.detail.trim();
  return null;
}

/**
 * Get error_code from response data for UI handling (modals, etc.).
 */
export function getErrorCode(data) {
  if (!data || typeof data !== 'object') return null;
  return data.error_code || null;
}

/**
 * Centralized: parse structured error from response data.
 * Returns { userMessage, errorCode, details } for UI (modals, never raw JSON).
 */
export function parseApiError(data) {
  if (!data || typeof data !== 'object') {
    return { userMessage: 'Something went wrong. Please try again.', errorCode: null, details: null };
  }
  const errorCode = data.error_code || null;
  const userMessage = parseStructuredError(data) || (typeof data.detail === 'string' ? data.detail : null) || 'Something went wrong. Please try again.';
  const details = data.details != null ? data.details : null;
  const codeToMessage = {
    PLAN_LIMIT_EXCEEDED: 'You have reached your monthly run limit. Upgrade your plan or try again next month.',
    VALIDATION_TIMEOUT: 'The validation did not complete in time. Please try again with a smaller programme or try again later.',
    VALIDATION_GUARDRAIL_ERROR: 'An internal consistency check failed. Please try again or contact support.',
    RATE_LIMIT_EXCEEDED: 'Too many requests. Please wait a moment and try again.',
    UNAUTHORIZED: 'Your session has expired. Please sign in again.',
  };
  const fallback = codeToMessage[errorCode] || userMessage;
  return { userMessage: fallback, errorCode, details };
}

function getMessage(err) {
  if (err.response?.data?.detail) {
    const d = err.response.data.detail;
    return typeof d === 'string' ? d : (d.msg || JSON.stringify(d));
  }
  if (err.code === 'ERR_NETWORK' || err.message === 'Network Error') {
    return 'Unable to connect to the server. Please check that the backend is running and try again.';
  }
  return err.message || 'Something went wrong. Please try again.';
}

/**
 * Auth: signup. After email verification is enabled, returns { message, email } (no token until verified).
 */
export async function apiSignup(email, password, name, organisation) {
  const response = await fetch(`${API_BASE}/api/auth/signup`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      email: email.trim(),
      password,
      name: (name || '').trim(),
      organisation: (organisation || '').trim(),
    }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data.detail;
    const msg = typeof detail === 'string' ? detail : (detail?.message || 'Sign up failed.');
    throw new Error(msg);
  }
  return data;
}

/**
 * Auth: login. Returns { access_token, user }. Throws with errorCode 'EMAIL_NOT_VERIFIED' when 403.
 */
export async function apiLogin(email, password) {
  const response = await fetch(`${API_BASE}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: email.trim(), password }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data.detail;
    const msg = typeof detail === 'string' ? detail : (detail?.message || 'Login failed.');
    const err = new Error(msg);
    if (response.status === 403 && detail?.error_code === 'EMAIL_NOT_VERIFIED') {
      err.errorCode = 'EMAIL_NOT_VERIFIED';
    }
    throw err;
  }
  return data;
}

/**
 * Auth: get current user. Requires token. Returns user or null.
 */
export async function apiGetMe() {
  const token = getAuthToken();
  if (!token) return null;
  const response = await fetch(`${API_BASE}/api/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (checkUnauthorized(response)) return null;
  if (!response.ok) return null;
  return response.json();
}

/**
 * Auth: update current user. Requires token.
 */
export async function apiUpdateMe(updates) {
  const response = await fetch(`${API_BASE}/api/auth/me`, {
    method: 'PATCH',
    headers: authHeaders(),
    body: JSON.stringify(updates),
  });
  if (checkUnauthorized(response)) throw new Error('Session expired. Please sign in again.');
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || 'Update failed.');
  return data;
}

/**
 * Analyze contract (PDF or DOCX). Returns analysis result or throws with user message.
 */
export async function analyzeContract(file) {
  const formData = new FormData();
  formData.append('file', file);
  const response = await fetch(`${API_BASE}/api/v1/analyze_contract`, {
    method: 'POST',
    body: formData,
    headers: {}, // let browser set Content-Type for multipart
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail = body.detail || response.statusText;
    throw new Error(typeof detail === 'string' ? detail : detail.msg || 'Contract analysis failed.');
  }
  return response.json();
}

/**
 * Fetch the latest contract analysis JSON from the server (last saved by analyze_contract).
 * Use when Compare shows 0 required activities but the contract has them.
 */
export async function apiGetLatestContractAnalysis() {
  const response = await fetch(`${API_BASE}/api/latest_contract_analysis`, {
    headers: getAuthToken() ? { Authorization: `Bearer ${getAuthToken()}` } : {},
  });
  if (checkUnauthorized(response)) throw new Error('Session expired. Please sign in again.');
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || response.statusText || 'No contract analysis on server.');
  }
  return response.json();
}

/**
 * Validate programme (XER) against contract. contractAnalysisJson from analyze_contract.
 * previousXerFile: optional File for submission comparison (compare with previous programme).
 * Uses auth header when token present so backend can create/update run and enforce plan limits.
 */
export async function validateProgramme(xerFile, contractAnalysisJson, previousXerFile = null) {
  const formData = new FormData();
  formData.append('xer_file', xerFile);
  if (contractAnalysisJson) {
    const blob = new Blob([JSON.stringify(contractAnalysisJson)], { type: 'application/json' });
    formData.append('json_file', blob, 'contract_analysis.json');
  }
  if (previousXerFile && previousXerFile instanceof File) {
    formData.append('previous_xer_file', previousXerFile);
  }
  const headers = {};
  const token = getAuthToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(`${API_BASE}/api/v1/validate_programme`, {
    method: 'POST',
    body: formData,
    headers,
  });
  if (checkUnauthorized(response)) throw new Error('Session expired. Please sign in again.');
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const code = getErrorCode(body);
    const msg = parseStructuredError(body) || body.detail || response.statusText || 'Programme validation failed.';
    const err = new Error(typeof msg === 'string' ? msg : 'Programme validation failed.');
    err.errorCode = code;
    err.details = body.details;
    throw err;
  }
  return response.json();
}

/**
 * Generate report (PDF/DOCX) from validation result. Returns blob for download.
 * options: { confidentiality_mode?, organisation_logo_url?, user_name?, run_id? }
 */
export async function generateReport(validationResult, format = 'pdf', options = {}) {
  const blob = new Blob([JSON.stringify(validationResult)], { type: 'application/json' });
  const formData = new FormData();
  formData.append('json_file', blob, 'validation.json');
  if (options.confidentiality_mode === true) formData.append('confidentiality_mode', 'true');
  if (options.organisation_logo_url) formData.append('organisation_logo_url', options.organisation_logo_url);
  if (options.user_name) formData.append('user_name', options.user_name);
  if (options.run_id != null) formData.append('run_id', String(options.run_id));
  const url = `${API_BASE}/api/v1/generate_report?format=${encodeURIComponent(format)}`;
  const headers = {};
  const token = getAuthToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(url, {
    method: 'POST',
    body: formData,
    headers,
  });
  if (checkUnauthorized(response)) throw new Error('Session expired. Please sign in again.');
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const parsed = parseApiError(body);
    const err = new Error(parsed.userMessage);
    err.errorCode = parsed.errorCode;
    err.details = parsed.details;
    throw err;
  }
  return response.blob();
}

/**
 * Build validation report structure (same as PDF). Returns the structured sections for web preview.
 */
export async function buildValidationReport(validationResult) {
  const response = await fetch(`${API_BASE}/api/v1/build_validation_report`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(validationResult),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail = body.detail || response.statusText;
    throw new Error(typeof detail === 'string' ? detail : detail.msg || 'Could not build report preview.');
  }
  return response.json();
}

/**
 * Analysis runs (saved under user account).
 */

/**
 * List current user's analysis runs. Requires auth. Returns [] on error or 401.
 */
export async function apiListRuns() {
  const response = await fetch(`${API_BASE}/api/runs`, {
    headers: authHeaders(),
  });
  if (checkUnauthorized(response)) throw new Error('Session expired. Please sign in again.');
  if (!response.ok) return [];
  const data = await response.json().catch(() => []);
  return Array.isArray(data) ? data : [];
}

/**
 * Save a new analysis run. Requires auth. Returns created run or throws.
 */
export async function apiCreateRun({ contractName, programmeName, contractAnalysis, validationResult, status }) {
  const response = await fetch(`${API_BASE}/api/runs`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({
      contract_name: contractName || 'Contract',
      programme_name: programmeName || null,
      contract_analysis: contractAnalysis || null,
      validation_result: validationResult || null,
      status: status || undefined,
    }),
  });
  if (checkUnauthorized(response)) throw new Error('Session expired. Please sign in again.');
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(parseStructuredError(data) || 'Failed to save analysis run.');
  return data;
}

/**
 * Get one run by id. Requires auth. Returns null if not found.
 */
export async function apiGetRun(runId) {
  const response = await fetch(`${API_BASE}/api/runs/${runId}`, {
    headers: authHeaders(),
  });
  if (checkUnauthorized(response)) throw new Error('Session expired. Please sign in again.');
  if (!response.ok) return null;
  return response.json();
}

/**
 * Delete an analysis run. Requires auth.
 */
export async function apiDeleteRun(runId) {
  const response = await fetch(`${API_BASE}/api/runs/${runId}`, {
    method: 'DELETE',
    headers: authHeaders(),
  });
  if (checkUnauthorized(response)) throw new Error('Session expired. Please sign in again.');
  if (!response.ok && response.status !== 204) {
    const data = await response.json().catch(() => ({}));
    throw new Error(parseStructuredError(data) || 'Failed to delete run.');
  }
}

/**
 * Delete all analysis runs for the current user. Requires auth.
 */
export async function apiDeleteAllRuns() {
  const response = await fetch(`${API_BASE}/api/runs`, {
    method: 'DELETE',
    headers: authHeaders(),
  });
  if (checkUnauthorized(response)) throw new Error('Session expired. Please sign in again.');
  if (!response.ok && response.status !== 204) {
    const data = await response.json().catch(() => ({}));
    throw new Error(parseStructuredError(data) || 'Failed to delete all runs.');
  }
}

/**
 * Export analysis history (summary list). Requires auth.
 */
export async function apiExportRuns() {
  const response = await fetch(`${API_BASE}/api/runs/export`, {
    headers: authHeaders(),
  });
  if (checkUnauthorized(response)) throw new Error('Session expired. Please sign in again.');
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(parseStructuredError(data) || 'Failed to export.');
  }
  return response.json();
}

/**
 * Health check (optional, for connection status).
 */
export async function healthCheck() {
  try {
    const r = await fetch(`${API_BASE}/health`);
    return r.ok ? await r.json() : null;
  } catch {
    return null;
  }
}

/**
 * Verify email with token from link. Returns { message, email } or throws.
 */
export async function apiVerifyEmail(token) {
  const url = `${API_BASE}/api/auth/verify-email?token=${encodeURIComponent(token)}`;
  const response = await fetch(url);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data.detail;
    const msg = typeof detail === 'string' ? detail : (detail?.message || 'Verification failed.');
    const err = new Error(msg);
    err.errorCode = detail?.error_code;
    throw err;
  }
  return data;
}

/**
 * Request password reset. Sends email with reset link. Returns { message }.
 */
export async function apiRequestPasswordReset(email) {
  const response = await fetch(`${API_BASE}/api/auth/request-password-reset`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: (email || '').trim().toLowerCase() }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data.detail;
    throw new Error(typeof detail === 'string' ? detail : (detail?.message || 'Request failed.'));
  }
  return data;
}

/**
 * Reset password with token from email. Returns { message }.
 */
export async function apiResetPassword(token, newPassword) {
  const response = await fetch(`${API_BASE}/api/auth/reset-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token: (token || '').trim(), new_password: newPassword }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data.detail;
    const err = new Error(typeof detail === 'string' ? detail : (detail?.message || 'Reset failed.'));
    err.errorCode = detail?.error_code;
    throw err;
  }
  return data;
}

/**
 * Resend verification email. Returns { message }.
 */
export async function apiResendVerification(email) {
  const response = await fetch(`${API_BASE}/api/auth/resend-verification`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: (email || '').trim().toLowerCase() }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data.detail;
    throw new Error(typeof detail === 'string' ? detail : (detail?.message || 'Failed to resend.'));
  }
  return data;
}

export { getMessage };
