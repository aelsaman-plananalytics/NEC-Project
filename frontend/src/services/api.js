/**
 * API service for NEC Engineering Analysis.
 * All backend calls go through here. User-facing error messages only.
 */

const API_BASE = process.env.REACT_APP_API_URL || 'http://127.0.0.1:8000';

const AUTH_TOKEN_KEY = 'nec_analysis_token';

export function getAuthToken() {
  return localStorage.getItem(AUTH_TOKEN_KEY);
}

export function setAuthToken(token) {
  if (token) localStorage.setItem(AUTH_TOKEN_KEY, token);
  else localStorage.removeItem(AUTH_TOKEN_KEY);
}

function authHeaders() {
  const token = getAuthToken();
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
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
 * Auth: signup. Returns { access_token, user }.
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
    throw new Error(data.detail || 'Sign up failed.');
  }
  return data;
}

/**
 * Auth: login. Returns { access_token, user }.
 */
export async function apiLogin(email, password) {
  const response = await fetch(`${API_BASE}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: email.trim(), password }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || 'Login failed.');
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
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || 'Update failed.');
  }
  return data;
}

/**
 * Analyze contract (PDF or DOCX). Returns analysis result or throws with user message.
 */
export async function analyzeContract(file) {
  const formData = new FormData();
  formData.append('file', file);
  const response = await fetch(`${API_BASE}/api/analyze_contract`, {
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
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || response.statusText || 'No contract analysis on server.');
  }
  return response.json();
}

/**
 * Validate programme (XER) against contract. contractAnalysisJson is the object from analyze_contract.
 */
export async function validateProgramme(xerFile, contractAnalysisJson) {
  const formData = new FormData();
  formData.append('xer_file', xerFile);
  if (contractAnalysisJson) {
    const blob = new Blob([JSON.stringify(contractAnalysisJson)], { type: 'application/json' });
    formData.append('json_file', blob, 'contract_analysis.json');
  }
  const response = await fetch(`${API_BASE}/api/validate_programme`, {
    method: 'POST',
    body: formData,
    headers: {},
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail = body.detail || response.statusText;
    throw new Error(typeof detail === 'string' ? detail : detail.msg || 'Programme validation failed.');
  }
  return response.json();
}

/**
 * Generate report (PDF) from validation result. Returns blob for download.
 */
export async function generateReport(validationResult, format = 'pdf') {
  const blob = new Blob([JSON.stringify(validationResult)], { type: 'application/json' });
  const formData = new FormData();
  formData.append('json_file', blob, 'validation.json');
  const url = `${API_BASE}/api/generate_report?format=${encodeURIComponent(format)}`;
  const response = await fetch(url, {
    method: 'POST',
    body: formData,
    headers: {},
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail = body.detail || response.statusText;
    throw new Error(typeof detail === 'string' ? detail : detail.msg || 'Report generation failed.');
  }
  return response.blob();
}

/**
 * Build validation report structure (same as PDF). Returns the structured sections for web preview.
 */
export async function buildValidationReport(validationResult) {
  const response = await fetch(`${API_BASE}/api/build_validation_report`, {
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
  if (!response.ok) return [];
  const data = await response.json().catch(() => []);
  return Array.isArray(data) ? data : [];
}

/**
 * Save a new analysis run. Requires auth. Returns created run or throws.
 */
export async function apiCreateRun({ contractName, programmeName, contractAnalysis, validationResult }) {
  const response = await fetch(`${API_BASE}/api/runs`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({
      contract_name: contractName || 'Contract',
      programme_name: programmeName || null,
      contract_analysis: contractAnalysis || null,
      validation_result: validationResult || null,
    }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || 'Failed to save analysis run.');
  }
  return data;
}

/**
 * Get one run by id. Requires auth. Returns null if not found.
 */
export async function apiGetRun(runId) {
  const response = await fetch(`${API_BASE}/api/runs/${runId}`, {
    headers: authHeaders(),
  });
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
  if (!response.ok && response.status !== 204) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || 'Failed to delete run.');
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
  if (!response.ok && response.status !== 204) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || 'Failed to delete all runs.');
  }
}

/**
 * Export analysis history (summary list). Requires auth.
 */
export async function apiExportRuns() {
  const response = await fetch(`${API_BASE}/api/runs/export`, {
    headers: authHeaders(),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || 'Failed to export.');
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

export { getMessage };
