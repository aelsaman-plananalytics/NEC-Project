import React from 'react';

/**
 * Modal for structured errors: PLAN_LIMIT_EXCEEDED, VALIDATION_TIMEOUT, etc.
 * Never shows raw JSON.
 */
export default function ErrorModal({ errorCode, message, details, onClose }) {
  const title =
    errorCode === 'PLAN_LIMIT_EXCEEDED'
      ? 'Monthly run limit reached'
      : errorCode === 'VALIDATION_TIMEOUT'
        ? 'Validation took too long'
        : errorCode === 'VALIDATION_GUARDRAIL_ERROR'
          ? 'Internal consistency error'
          : errorCode === 'RATE_LIMIT_EXCEEDED'
            ? 'Too many requests'
            : errorCode === 'UNAUTHORIZED'
              ? 'Session expired'
              : 'Something went wrong';

  const body =
    errorCode === 'PLAN_LIMIT_EXCEEDED'
      ? (message || 'You have reached your monthly run limit. Upgrade your plan or try again next month.')
      : errorCode === 'VALIDATION_TIMEOUT'
        ? (message || 'The validation did not complete in time. Please try again with a smaller programme or try again later.')
        : errorCode === 'VALIDATION_GUARDRAIL_ERROR'
          ? (message || 'An internal consistency check failed. Please try again or contact support.')
          : errorCode === 'RATE_LIMIT_EXCEEDED'
            ? (message || 'Too many requests. Please wait a moment and try again.')
            : errorCode === 'UNAUTHORIZED'
              ? (message || 'Your session has expired. Please sign in again.')
              : message || 'Please try again.';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50" role="dialog" aria-modal="true" aria-labelledby="error-modal-title">
      <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6">
        <h2 id="error-modal-title" className="text-lg font-semibold text-slate-900 mb-2">
          {title}
        </h2>
        <p className="text-slate-700 text-sm mb-4">{body}</p>
        {details?.monthly_run_limit != null && (
          <p className="text-slate-600 text-xs mb-2">Limit: {details.monthly_run_limit} runs per month.</p>
        )}
        <button
          type="button"
          onClick={onClose}
          className="w-full px-4 py-2 rounded-lg bg-amber-500 text-slate-900 font-medium hover:bg-amber-400"
        >
          OK
        </button>
      </div>
    </div>
  );
}
