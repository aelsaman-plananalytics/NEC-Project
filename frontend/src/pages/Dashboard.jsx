import React, { useState, useMemo } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { usePipeline } from '../context/PipelineContext';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { apiGetRun, generateReport, parseApiError } from '../services/api';
import { getRunStatusDisplay } from '../utils/runStatus';
import { humanizeTime } from '../utils/timeUtils';

const STATUS_FILTER_OPTIONS = [
  { value: '', label: 'All' },
  { value: 'acceptable', label: 'Acceptable' },
  { value: 'not_acceptable', label: 'Not acceptable' },
  { value: 'processing', label: 'Processing' },
  { value: 'failed', label: 'Failed' },
];

export default function Dashboard() {
  const navigate = useNavigate();
  const { addToast } = useToast();
  const { history, removeFromHistory, resetPipeline, loadSavedRun, contractAnalysis } = usePipeline();
  const { user } = useAuth();
  const [openingId, setOpeningId] = useState(null);
  const [downloadId, setDownloadId] = useState(null);
  const [openError, setOpenError] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('');

  const filteredHistory = useMemo(() => {
    let list = history;
    if (searchQuery.trim()) {
      const q = searchQuery.trim().toLowerCase();
      list = list.filter((e) => (e.programmeName || '').toLowerCase().includes(q) || (e.contractName || '').toLowerCase().includes(q));
    }
    if (statusFilter) {
      if (statusFilter === 'acceptable') {
        list = list.filter((e) => (e.status || 'completed') === 'completed' && (e.acceptabilityStatus || '').toUpperCase() === 'ACCEPTABLE');
      } else if (statusFilter === 'not_acceptable') {
        list = list.filter((e) => (e.status || 'completed') === 'completed' && ((e.acceptabilityStatus || '').toUpperCase() === 'NOT_ACCEPTABLE' || (e.acceptabilityStatus || '').toUpperCase() === 'NOT ACCEPTABLE'));
      } else if (statusFilter === 'processing') {
        list = list.filter((e) => (e.status || '').toLowerCase() === 'processing');
      } else if (statusFilter === 'failed') {
        list = list.filter((e) => (e.status || '').toLowerCase() === 'failed' || (e.status || '').toLowerCase() === 'timed_out');
      }
    }
    return list;
  }, [history, searchQuery, statusFilter]);

  const handleStartNewAnalysis = () => {
    resetPipeline();
    navigate('/analysis');
  };

  const handleOpenAnalysis = async (entryId) => {
    setOpenError('');
    setOpeningId(entryId);
    try {
      const run = await apiGetRun(entryId);
      if (!run) {
        setOpenError('Analysis not found.');
        return;
      }
      loadSavedRun(run);
      if (run.validation_result) {
        navigate('/review');
      } else {
        navigate('/analysis');
      }
    } catch (err) {
      setOpenError(err.message || 'Could not open analysis.');
    } finally {
      setOpeningId(null);
    }
  };

  const handleDownloadPdf = async (entryId) => {
    setOpenError('');
    setDownloadId(entryId);
    try {
      const run = await apiGetRun(entryId);
      if (!run || !run.validation_result) {
        setOpenError('No report available for this run.');
        return;
      }
      const opts = {
        confidentiality_mode: user?.preferences?.confidentiality_mode === true,
        organisation_logo_url: user?.organisationLogoUrl || null,
        user_name: user?.name || null,
        run_id: run.id,
      };
      const blob = await generateReport(run.validation_result, 'pdf', opts);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `validation_report_${run.contract_name || 'run'}_${entryId}.pdf`.replace(/\s+/g, '_');
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      const parsed = parseApiError({
        error_code: err.errorCode,
        error_message: err.message,
        details: err.details,
      });
      setOpenError(parsed.userMessage);
      const toastCodes = ['PLAN_LIMIT_EXCEEDED', 'VALIDATION_TIMEOUT', 'RATE_LIMIT_EXCEEDED'];
      if (toastCodes.includes(parsed.errorCode)) {
        addToast({ type: 'error', message: parsed.userMessage });
      }
    } finally {
      setDownloadId(null);
    }
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <h1 className="font-heading text-2xl font-bold text-slate-900 mb-2">Dashboard</h1>
      <p className="text-slate-600 mb-8">
        {user?.name ? `Welcome back, ${user.name}.` : 'Welcome.'} Start a new analysis or open one from your history.
      </p>

      <div className="mb-10 flex flex-wrap gap-3">
        <button
          type="button"
          onClick={handleStartNewAnalysis}
          className="inline-flex items-center justify-center px-8 py-4 rounded-xl bg-amber-500 text-slate-900 font-semibold text-lg hover:bg-amber-400 transition-colors"
        >
          Start new analysis
        </button>
        {contractAnalysis && (
          <button
            type="button"
            onClick={() => navigate('/compare')}
            className="inline-flex items-center justify-center px-6 py-4 rounded-xl border border-slate-300 text-slate-700 font-medium hover:bg-slate-50 transition-colors"
          >
            Compare two programmes
          </button>
        )}
      </div>

      <section>
        <h2 className="font-heading text-lg font-semibold text-slate-800 mb-4">Recent analyses</h2>
        {history.length > 0 && (
          <div className="mb-4 flex flex-wrap gap-3">
            <input
              type="search"
              placeholder="Filter by programme name…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="px-3 py-2 rounded-lg border border-slate-300 text-slate-700 text-sm w-64 max-w-full focus:ring-2 focus:ring-amber-500 focus:border-amber-500"
              aria-label="Search by programme name"
            />
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="px-3 py-2 rounded-lg border border-slate-300 text-slate-700 text-sm bg-white focus:ring-2 focus:ring-amber-500 focus:border-amber-500"
              aria-label="Filter by status"
            >
              {STATUS_FILTER_OPTIONS.map((opt) => (
                <option key={opt.value || 'all'} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </div>
        )}
        {openError && (
          <p className="text-sm text-red-600 mb-3" role="alert">
            {openError}
          </p>
        )}
        {history.length === 0 ? (
          <p className="text-slate-600 text-sm">If you haven&apos;t validated a programme yet, start by uploading one.</p>
        ) : filteredHistory.length === 0 ? (
          <p className="text-slate-600 text-sm">No analyses match your filters.</p>
        ) : (
          <ul className="space-y-3">
            {filteredHistory.map((entry) => (
              <li
                key={entry.id}
                className="flex items-center justify-between p-4 rounded-lg bg-white border border-slate-200 transition-shadow hover:shadow-md"
              >
                <div className="min-w-0 flex-1">
                  <p className="font-medium text-slate-900">
                    {entry.contractName || 'Contract'} {entry.programmeName ? `· ${entry.programmeName}` : ''}
                  </p>
                  <p className="text-sm text-slate-500">
                    {entry.createdAt ? humanizeTime(entry.createdAt) : ''}
                  </p>
                  <div className="flex flex-wrap gap-2 mt-2">
                    {(() => {
                      const { label, className } = getRunStatusDisplay(entry.status, entry.acceptabilityStatus);
                      return (
                        <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${className}`}>
                          {label}
                        </span>
                      );
                    })()}
                    {entry.submissionStage != null && entry.submissionStage !== '' && (
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-700">
                        {String(entry.submissionStage)}
                      </span>
                    )}
                    {entry.hasComparison && (
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800">
                        Comparison
                      </span>
                    )}
                  </div>
                </div>
                <div className="flex flex-wrap items-center gap-2 flex-shrink-0">
                  <Link
                    to={`/runs/${entry.id}`}
                    className="text-sm font-medium text-slate-700 hover:text-slate-900 border border-slate-300 px-2 py-1 rounded hover:bg-slate-50 transition-colors"
                  >
                    View details
                  </Link>
                  <button
                    type="button"
                    onClick={() => handleOpenAnalysis(entry.id)}
                    disabled={openingId != null}
                    className="text-sm font-medium text-amber-600 hover:text-amber-700 disabled:opacity-50 transition-colors"
                    aria-label="Open this analysis"
                  >
                    {openingId === entry.id ? 'Opening…' : 'Open'}
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDownloadPdf(entry.id)}
                    disabled={downloadId != null || entry.status !== 'completed'}
                    className="text-sm font-medium text-slate-700 hover:text-slate-900 disabled:opacity-50 transition-colors"
                    aria-label="Download PDF"
                  >
                    {downloadId === entry.id ? 'Preparing…' : 'Download PDF'}
                  </button>
                  <button
                    type="button"
                    onClick={() => navigate('/compare')}
                    className="text-sm font-medium text-slate-600 hover:text-slate-800 transition-colors"
                    aria-label="Compare programmes"
                  >
                    Compare
                  </button>
                  <button
                    type="button"
                    onClick={() => removeFromHistory(entry.id)}
                    className="text-sm text-slate-500 hover:text-red-600 transition-colors"
                    aria-label="Remove from history"
                  >
                    Remove
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
