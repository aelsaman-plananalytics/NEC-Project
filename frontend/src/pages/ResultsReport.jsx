import React, { useState, useCallback, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { usePipeline } from '../context/PipelineContext';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { generateReport, parseApiError } from '../services/api';
import { buildResultsForReport, getAcceptabilityLabel } from '../utils/validationSummary';

export default function ResultsReport() {
  const navigate = useNavigate();
  const { addToast } = useToast();
  const { validationResult, contractAnalysis, contractFile, programmeFile, userConfirmations, resetPipeline, addToHistory } = usePipeline();
  const { user } = useAuth();
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState('');
  const [comparisonExpanded, setComparisonExpanded] = useState(true);
  const [alignedExpanded, setAlignedExpanded] = useState(true);
  const [unalignedExpanded, setUnalignedExpanded] = useState(true);
  const submissionComparison = validationResult?.submission_comparison ?? null;
  const vs = validationResult?.validation_summary ?? {};
  const alignment = validationResult?.alignment?.scope_coverage ?? {};
  const obligationsReport = alignment.obligations_report || [];
  const currentBlockers = obligationsReport.filter((ob) => ob.aligned === false);
  const becameAlignedCount = Array.isArray(submissionComparison?.became_aligned) ? submissionComparison.became_aligned.length : 0;
  const becameUnalignedCount = Array.isArray(submissionComparison?.became_unaligned) ? submissionComparison.became_unaligned.length : 0;

  const contractName = (contractFile?.name || contractAnalysis?.project || 'Contract').replace(/\.[^.]+$/, '');
  const dateStr = new Date().toISOString().slice(0, 10);

  const defaultFormat = (user?.preferences?.default_report_format || 'pdf').toLowerCase();
  const autoDownload = user?.preferences?.auto_download_report === true;

  const getReportFilename = useCallback((format) => {
    const ext = format === 'docx' ? 'docx' : 'pdf';
    const pref = user?.reportNamingPreference || 'contract_date_validation';
    if (pref === 'date_only') return `Programme_Validation_${dateStr}.${ext}`;
    return `${contractName}_${dateStr}_Programme_Validation.${ext}`;
  }, [user?.reportNamingPreference, contractName, dateStr]);

  const payloadForReport = useCallback(() => {
    const base = { ...validationResult };
    if (userConfirmations && userConfirmations.length > 0) {
      base.user_confirmations = userConfirmations.map((c) => ({
        finding_id: c.findingId,
        confirmed: c.confirmed,
        note: c.note,
        timestamp: c.timestamp,
      }));
    }
    return base;
  }, [validationResult, userConfirmations]);

  const handleDownload = useCallback(async (format = null) => {
    if (!validationResult) return;
    const fmt = (format || defaultFormat) === 'docx' ? 'docx' : 'pdf';
    setDownloading(true);
    setDownloadError('');
    try {
      const opts = {
        confidentiality_mode: user?.preferences?.confidentiality_mode === true,
        organisation_logo_url: user?.organisationLogoUrl || null,
        user_name: user?.name || null,
      };
      const blob = await generateReport(payloadForReport(), fmt, opts);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = getReportFilename(fmt);
      a.click();
      URL.revokeObjectURL(url);
      addToHistory({
        contractName: contractAnalysis?.project || contractFile?.name,
        programmeName: programmeFile?.name || null,
        validationResult: true,
      });
      addToast({ type: 'success', message: 'Report generated successfully.' });
    } catch (err) {
      const parsed = parseApiError({
        error_code: err.errorCode,
        error_message: err.message,
        details: err.details,
      });
      setDownloadError(parsed.userMessage);
      const toastCodes = ['PLAN_LIMIT_EXCEEDED', 'VALIDATION_TIMEOUT', 'RATE_LIMIT_EXCEEDED'];
      if (toastCodes.includes(parsed.errorCode)) {
        addToast({ type: 'error', message: parsed.userMessage });
      }
    } finally {
      setDownloading(false);
    }
  }, [validationResult, payloadForReport, getReportFilename, addToHistory, contractAnalysis, contractFile, programmeFile, user, defaultFormat, addToast]);

  const [downloadFormat, setDownloadFormat] = useState('pdf');
  const hasAutoDownloaded = React.useRef(false);
  useEffect(() => {
    if (user && defaultFormat) setDownloadFormat(defaultFormat);
  }, [user, defaultFormat]);
  useEffect(() => {
    if (autoDownload && validationResult && user && !hasAutoDownloaded.current) {
      hasAutoDownloaded.current = true;
      handleDownload(defaultFormat);
    }
  }, [autoDownload, validationResult, user, defaultFormat, handleDownload]);

  if (!validationResult) {
    navigate('/dashboard', { replace: true });
    return null;
  }

  const reportContent = buildResultsForReport(validationResult);

  const handleStartNew = () => {
    resetPipeline();
    navigate('/analysis');
  };

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <h1 className="font-heading text-2xl font-bold text-slate-900 mb-2">Results and report</h1>
      <p className="text-slate-600 mb-6">
        Your NEC Clause 31 programme validation is complete. Below is the executive summary. Download the full report as a PDF to share or file.
      </p>

      <div className="space-y-6">
        <section className="bg-slate-50 border border-slate-200 rounded-xl p-4 mb-4">
          <h2 className="font-semibold text-slate-800 mb-2 text-sm uppercase tracking-wide">Summary</h2>
          <p className="text-slate-700">
            <strong>Acceptability:</strong> {getAcceptabilityLabel(vs.acceptability_status)}
          </p>
          {submissionComparison && (submissionComparison.status_change != null && submissionComparison.status_change !== '') && (
            <p className="text-slate-700 mt-1">
              <strong>Status change:</strong> {String(submissionComparison.status_change)}
            </p>
          )}
          <ul className="mt-2 text-sm text-slate-600 space-y-0.5">
            {becameAlignedCount > 0 && <li>Became aligned: {becameAlignedCount}</li>}
            {becameUnalignedCount > 0 && <li>Became unaligned: {becameUnalignedCount}</li>}
            {currentBlockers.length > 0 && <li>Current blockers: {currentBlockers.length}</li>}
          </ul>
        </section>

        <section className="bg-white border border-slate-200 rounded-xl p-6">
          <h2 className="font-semibold text-slate-800 mb-2">NEC Engineering Analysis — Executive summary</h2>
          <p className="text-slate-700 font-medium">{reportContent.programmeDecisionText}</p>
          {reportContent.programmeDecisionDetail && (
            <p className="text-slate-600 mt-2">{reportContent.programmeDecisionDetail}</p>
          )}
          {reportContent.qualitySummary && (
            <p className="text-slate-600 mt-2 text-sm">{reportContent.qualitySummary}</p>
          )}
        </section>

        {reportContent.failureReasons && reportContent.failureReasons.length > 0 && (
          <section className="bg-amber-50/50 border border-amber-200 rounded-xl p-6">
            <h2 className="font-semibold text-slate-800 mb-2">Required actions</h2>
            <p className="text-slate-600 text-sm mb-2">The following items should be addressed for the programme to be acceptable:</p>
            <ul className="list-disc pl-6 text-slate-700 text-sm space-y-1">
              {reportContent.failureReasons.map((r, i) => (
                <li key={i}>{typeof r === 'string' ? r : (r?.text ?? r?.message ?? r?.reason ?? '—')}</li>
              ))}
            </ul>
          </section>
        )}

        {reportContent.requiredActions && reportContent.requiredActions.length > 0 && (
          <section className="bg-slate-50 border border-slate-200 rounded-xl p-6">
            <h2 className="font-semibold text-slate-800 mb-2">Next steps</h2>
            <ul className="list-disc pl-6 text-slate-700 text-sm space-y-1">
              {reportContent.requiredActions.map((action, i) => (
                <li key={i}>{typeof action === 'string' ? action : (action?.text ?? action?.message ?? action?.reason ?? '—')}</li>
              ))}
            </ul>
          </section>
        )}

        {submissionComparison && (
          <section className="bg-slate-50 border border-slate-200 rounded-xl overflow-hidden">
            <button
              type="button"
              onClick={() => setComparisonExpanded((e) => !e)}
              className="w-full flex items-center justify-between p-4 text-left font-semibold text-slate-800 hover:bg-slate-100 transition-colors"
            >
              Submission evolution
              <span className="text-slate-500 font-normal text-sm">
                {becameAlignedCount + becameUnalignedCount > 0 ? `(${becameAlignedCount} aligned, ${becameUnalignedCount} unaligned)` : ''} {comparisonExpanded ? '▼' : '▶'}
              </span>
            </button>
            {comparisonExpanded && (
              <div className="px-4 pb-4 space-y-4 text-sm text-slate-700 border-t border-slate-200 pt-4">
                {submissionComparison.previous_programme_name && (
                  <p><strong>Previous programme:</strong> {submissionComparison.previous_programme_name}</p>
                )}
                {submissionComparison.status_change != null && submissionComparison.status_change !== undefined && submissionComparison.status_change !== '' && (
                  <p><strong>Status change:</strong> {String(submissionComparison.status_change)}</p>
                )}
                {Array.isArray(submissionComparison.became_aligned) && submissionComparison.became_aligned.length > 0 && (
                  <div>
                    <button type="button" className="flex items-center justify-between w-full text-left font-medium text-slate-800 mb-2" onClick={() => setAlignedExpanded((e) => !e)}>
                      Obligations that became aligned <span className="text-green-700 font-normal">({submissionComparison.became_aligned.length})</span>
                      <span className="text-slate-500">{alignedExpanded ? '▼' : '▶'}</span>
                    </button>
                    {alignedExpanded && (
                      <ul className="list-disc pl-5 space-y-1 text-slate-700">
                        {submissionComparison.became_aligned.map((o, i) => (
                          <li key={i}>
                            <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800 mr-2">
                              Aligned
                            </span>
                            {typeof o === 'object' && o?.obligation_name ? o.obligation_name : String(o)}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}
                {Array.isArray(submissionComparison.became_unaligned) && submissionComparison.became_unaligned.length > 0 && (
                  <div>
                    <button type="button" className="flex items-center justify-between w-full text-left font-medium text-slate-800 mb-2" onClick={() => setUnalignedExpanded((e) => !e)}>
                      Obligations that became unaligned <span className="text-red-700 font-normal">({submissionComparison.became_unaligned.length})</span>
                      <span className="text-slate-500">{unalignedExpanded ? '▼' : '▶'}</span>
                    </button>
                    {unalignedExpanded && (
                      <ul className="space-y-2">
                        {submissionComparison.became_unaligned.map((o, i) => (
                          <li key={i} className="p-3 rounded-lg bg-red-50 border border-red-100">
                            <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-800 mr-2">Unaligned</span>
                            <span className="font-medium text-slate-800">{typeof o === 'object' ? (o.obligation_name || o.obligation_id || '—') : String(o)}</span>
                            {typeof o === 'object' && o.required_action != null && o.required_action !== '' && (
                              <p className="mt-2 text-slate-700 text-sm">{o.required_action}</p>
                            )}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}
              </div>
            )}
          </section>
        )}

        {downloadError && (
          <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-red-800 text-sm">
            {downloadError}
          </div>
        )}

        <div className="flex flex-wrap gap-3 items-center">
          <select
            value={downloadFormat}
            onChange={(e) => setDownloadFormat(e.target.value)}
            className="px-3 py-2 rounded-lg border border-slate-300 text-slate-700 bg-white"
          >
            <option value="pdf">PDF</option>
            <option value="docx">DOCX</option>
          </select>
          <button
            type="button"
            onClick={() => handleDownload(downloadFormat)}
            disabled={downloading}
            className="px-6 py-3 rounded-lg bg-amber-500 text-slate-900 font-semibold hover:bg-amber-400 disabled:opacity-50 transition-colors"
          >
            {downloading ? 'Preparing download…' : `Download report (${downloadFormat.toUpperCase()})`}
          </button>
          <button
            type="button"
            onClick={() => handleDownload(downloadFormat)}
            disabled={downloading}
            className="px-6 py-3 rounded-lg border border-slate-300 text-slate-700 font-medium hover:bg-slate-50 disabled:opacity-50 transition-colors"
          >
            Regenerate report
          </button>
          <button
            type="button"
            onClick={handleStartNew}
            className="px-6 py-3 rounded-lg border border-slate-300 text-slate-700 font-medium hover:bg-slate-50 transition-colors"
          >
            Start new analysis
          </button>
        </div>
      </div>

      <p className="mt-6">
        <button
          type="button"
          onClick={() => navigate('/dashboard')}
          className="text-amber-600 font-medium hover:text-amber-700 transition-colors"
        >
          Back to dashboard
        </button>
      </p>
    </div>
  );
}
