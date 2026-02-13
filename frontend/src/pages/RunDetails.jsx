import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { apiGetRun, generateReport } from '../services/api';
import { getRunStatusDisplay } from '../utils/runStatus';
import { getAcceptabilityLabel, getOverallStatusLabel } from '../utils/validationSummary';
import Spinner from '../components/Spinner';

const TABS = ['Summary', 'Obligations', 'Submission Evolution', 'Diagnostics', 'Governance', 'Download'];

export default function RunDetails() {
  const { runId } = useParams();
  const [run, setRun] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState('Summary');
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState('');

  useEffect(() => {
    let cancelled = false;
    if (!runId) return;
    setLoading(true);
    setError('');
    apiGetRun(runId)
      .then((data) => {
        if (!cancelled) setRun(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message || 'Run not found.');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [runId]);

  const handleDownload = async () => {
    if (!run?.validation_result) return;
    setDownloading(true);
    setDownloadError('');
    try {
      const blob = await generateReport(run.validation_result, 'pdf', { run_id: run.id });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `validation_report_${(run.contract_name || 'run').replace(/\s+/g, '_')}_${runId}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setDownloadError(err.message || 'Download failed.');
    } finally {
      setDownloading(false);
    }
  };

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-8">
        <Spinner label="Loading run…" />
      </div>
    );
  }
  if (error || !run) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-8">
        <p className="text-red-600 mb-4">{error || 'Run not found.'}</p>
        <Link to="/dashboard" className="text-amber-600 font-medium hover:text-amber-700">Back to dashboard</Link>
      </div>
    );
  }

  const vr = run.validation_result || {};
  const vs = vr.validation_summary || {};
  const statusDisplay = getRunStatusDisplay(run.status || 'completed', vs.acceptability_status);
  const obligationsReport = (vr.alignment?.scope_coverage?.obligations_report) || [];
  const submissionComparison = vr.submission_comparison || null;
  const logicChecks = vr.logic_checks || {};
  const risks = vr.risks || vr.risk_summary || {};
  const governance = vr.governance || {};

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <div className="mb-6 flex items-center gap-4">
        <Link to="/dashboard" className="text-amber-600 font-medium hover:text-amber-700">← Dashboard</Link>
      </div>
      <h1 className="font-heading text-2xl font-bold text-slate-900 mb-1">Run details</h1>
      <p className="text-slate-600 mb-4">
        {run.contract_name || 'Contract'} {run.programme_name ? `· ${run.programme_name}` : ''}
      </p>
      <p className="text-sm text-slate-500 mb-6">
        {run.created_at ? new Date(run.created_at).toLocaleString() : ''}
        {' · '}
        <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${statusDisplay.className}`}>
          {statusDisplay.label}
        </span>
      </p>

      <nav className="flex flex-wrap gap-2 border-b border-slate-200 mb-6" aria-label="Tabs">
        {TABS.map((tab) => (
          <button
            key={tab}
            type="button"
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 text-sm font-medium rounded-t-lg border-b-2 -mb-px transition-colors ${
              activeTab === tab
                ? 'border-amber-500 text-amber-700 bg-amber-50/50'
                : 'border-transparent text-slate-600 hover:text-slate-900 hover:bg-slate-50'
            }`}
          >
            {tab}
          </button>
        ))}
      </nav>

      <div className="bg-white border border-slate-200 rounded-xl p-6 min-h-[200px]">
        {activeTab === 'Summary' && (
          <div className="space-y-4">
            <p><strong>Acceptability:</strong> {getAcceptabilityLabel(vs.acceptability_status)}</p>
            {vs.overall_status != null && vs.overall_status !== '' && <p><strong>Overall status:</strong> {getOverallStatusLabel(vs.overall_status)}</p>}
            {vs.programme_decision_text && <p className="text-slate-700">{vs.programme_decision_text}</p>}
            {vs.quality_summary && <p className="text-slate-600 text-sm">{vs.quality_summary}</p>}
            {!vr.validation_summary && <p className="text-slate-500">No validation summary for this run.</p>}
          </div>
        )}

        {activeTab === 'Obligations' && (
          <div className="space-y-3">
            {obligationsReport.length === 0 ? (
              <p className="text-slate-500">No obligations report.</p>
            ) : (
              <ul className="space-y-2 text-sm">
                {obligationsReport.map((ob, i) => (
                  <li key={i} className="p-3 rounded-lg bg-slate-50 border border-slate-100">
                    <span className="font-medium text-slate-800">{ob.obligation_name || ob.obligation_id || '—'}</span>
                    {ob.required_action != null && ob.required_action !== '' && (
                      <p className="mt-1 text-slate-600">{ob.required_action}</p>
                    )}
                    {ob.aligned != null && (
                      <span className={`ml-2 text-xs ${ob.aligned ? 'text-green-700' : 'text-amber-700'}`}>
                        {ob.aligned ? 'Aligned' : 'Not aligned'}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {activeTab === 'Submission Evolution' && (
          <div className="space-y-4">
            {!submissionComparison ? (
              <p className="text-slate-500">No submission comparison for this run.</p>
            ) : (
              <>
                {submissionComparison.previous_programme_name && (
                  <p><strong>Previous programme:</strong> {submissionComparison.previous_programme_name}</p>
                )}
                {submissionComparison.status_change != null && submissionComparison.status_change !== '' && (
                  <p><strong>Status change:</strong> {String(submissionComparison.status_change)}</p>
                )}
                {Array.isArray(submissionComparison.became_aligned) && submissionComparison.became_aligned.length > 0 && (
                  <div>
                    <p className="font-medium text-slate-800 mb-2">Became aligned</p>
                    <ul className="list-disc pl-5 text-sm text-slate-700 space-y-1">
                      {submissionComparison.became_aligned.map((o, i) => (
                        <li key={i}>{typeof o === 'object' && o?.obligation_name ? o.obligation_name : String(o)}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {Array.isArray(submissionComparison.became_unaligned) && submissionComparison.became_unaligned.length > 0 && (
                  <div>
                    <p className="font-medium text-slate-800 mb-2">Became unaligned</p>
                    <ul className="space-y-2 text-sm text-slate-700">
                      {submissionComparison.became_unaligned.map((o, i) => (
                        <li key={i} className="p-2 rounded bg-amber-50">
                          {typeof o === 'object' ? (o.obligation_name || o.obligation_id || '—') : String(o)}
                          {typeof o === 'object' && o.required_action && (
                            <span className="block text-amber-800 mt-1">{o.required_action}</span>
                          )}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {activeTab === 'Diagnostics' && (
          <div className="space-y-4 text-sm">
            {Object.keys(logicChecks).length === 0 && !vr.risks && !vr.risk_summary ? (
              <p className="text-slate-500">No diagnostics data.</p>
            ) : (
              <>
                {logicChecks.circular_dependencies?.cycles?.length > 0 && (
                  <div>
                    <p className="font-medium text-slate-800">Circular dependencies</p>
                    <pre className="mt-1 p-3 bg-slate-50 rounded text-xs overflow-auto max-h-40">
                      {JSON.stringify(logicChecks.circular_dependencies, null, 2)}
                    </pre>
                  </div>
                )}
                {vr.schedule_health && (
                  <div>
                    <p className="font-medium text-slate-800">Schedule health</p>
                    <pre className="mt-1 p-3 bg-slate-50 rounded text-xs overflow-auto max-h-40">
                      {JSON.stringify(vr.schedule_health, null, 2)}
                    </pre>
                  </div>
                )}
                {Object.keys(risks).length > 0 && (
                  <div>
                    <p className="font-medium text-slate-800">Risks</p>
                    <pre className="mt-1 p-3 bg-slate-50 rounded text-xs overflow-auto max-h-40">
                      {JSON.stringify(risks, null, 2)}
                    </pre>
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {activeTab === 'Governance' && (
          <div className="space-y-3 text-sm">
            {!governance.acceptance_history?.length && !governance.latest_acceptance_decision ? (
              <p className="text-slate-500">No governance data for this run.</p>
            ) : (
              <>
                {governance.latest_acceptance_decision != null && (
                  <p><strong>Latest acceptance decision:</strong> {String(governance.latest_acceptance_decision)}</p>
                )}
                {governance.latest_acceptance_comments != null && governance.latest_acceptance_comments !== '' && (
                  <p><strong>Comments:</strong> {String(governance.latest_acceptance_comments)}</p>
                )}
                {Array.isArray(governance.acceptance_history) && governance.acceptance_history.length > 0 && (
                  <ul className="list-disc pl-5 space-y-1">
                    {governance.acceptance_history.map((h, i) => (
                      <li key={i}>
                        {h.decision} {h.decided_by ? `by ${h.decided_by}` : ''} {h.decided_at ? `at ${h.decided_at}` : ''}
                      </li>
                    ))}
                  </ul>
                )}
              </>
            )}
          </div>
        )}

        {activeTab === 'Download' && (
          <div className="space-y-4">
            {run.status === 'completed' && run.validation_result ? (
              <>
                <p className="text-slate-700">Download the validation report as PDF.</p>
                {downloadError && <p className="text-red-600 text-sm">{downloadError}</p>}
                <button
                  type="button"
                  onClick={handleDownload}
                  disabled={downloading}
                  className="px-6 py-3 rounded-lg bg-amber-500 text-slate-900 font-semibold hover:bg-amber-400 disabled:opacity-50 transition-colors"
                >
                  {downloading ? 'Preparing…' : 'Download PDF'}
                </button>
              </>
            ) : (
              <p className="text-slate-500">Report not available for this run (e.g. processing, failed, or timed out).</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
