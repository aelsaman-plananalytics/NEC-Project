import React, { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { usePipeline } from '../context/PipelineContext';
import { useAuth } from '../context/AuthContext';
import { generateReport } from '../services/api';
import { buildResultsForReport } from '../utils/validationSummary';

export default function ResultsReport() {
  const navigate = useNavigate();
  const { validationResult, contractAnalysis, contractFile, programmeFile, userConfirmations, resetPipeline, addToHistory } = usePipeline();
  const { user } = useAuth();
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState('');

  const contractName = (contractFile?.name || contractAnalysis?.project || 'Contract').replace(/\.[^.]+$/, '');
  const dateStr = new Date().toISOString().slice(0, 10);

  const getReportFilename = useCallback(() => {
    const pref = user?.reportNamingPreference || 'contract_date_validation';
    if (pref === 'date_only') return `Programme_Validation_${dateStr}.pdf`;
    return `${contractName}_${dateStr}_Programme_Validation.pdf`;
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

  const handleDownload = useCallback(async () => {
    if (!validationResult) return;
    setDownloading(true);
    setDownloadError('');
    try {
      const blob = await generateReport(payloadForReport(), 'pdf');
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = getReportFilename();
      a.click();
      URL.revokeObjectURL(url);
      addToHistory({
        contractName: contractAnalysis?.project || contractFile?.name,
        programmeName: programmeFile?.name || null,
        validationResult: true,
      });
    } catch (err) {
      setDownloadError(err.message || 'Download failed. Please try again.');
    } finally {
      setDownloading(false);
    }
  }, [validationResult, userConfirmations, payloadForReport, getReportFilename, addToHistory, contractAnalysis, contractFile]);

  if (!validationResult) {
    navigate('/dashboard', { replace: true });
    return null;
  }

  const reportContent = buildResultsForReport(validationResult);

  const handleRegenerate = () => {
    setDownloadError('');
    handleDownload();
  };

  const handleStartNew = () => {
    resetPipeline();
    navigate('/analysis');
  };

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <h1 className="font-heading text-2xl font-bold text-slate-900 mb-2">Results and report</h1>
      <p className="text-slate-600 mb-6">
        Your programme validation is complete. Below is the executive summary. Download the full report as a PDF to share or file.
      </p>

      <div className="space-y-6">
        <section className="bg-white border border-slate-200 rounded-xl p-6">
          <h2 className="font-semibold text-slate-800 mb-2">System assessment — Executive summary</h2>
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
                <li key={i}>{typeof r === 'string' ? r : r.reason || r.text || ''}</li>
              ))}
            </ul>
          </section>
        )}

        {reportContent.requiredActions && reportContent.requiredActions.length > 0 && (
          <section className="bg-slate-50 border border-slate-200 rounded-xl p-6">
            <h2 className="font-semibold text-slate-800 mb-2">Next steps</h2>
            <ul className="list-disc pl-6 text-slate-700 text-sm space-y-1">
              {reportContent.requiredActions.map((action, i) => (
                <li key={i}>{typeof action === 'string' ? action : (action?.text || action?.message || String(action))}</li>
              ))}
            </ul>
          </section>
        )}

        {downloadError && (
          <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-red-800 text-sm">
            {downloadError}
          </div>
        )}

        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            onClick={handleDownload}
            disabled={downloading}
            className="px-6 py-3 rounded-lg bg-amber-500 text-slate-900 font-semibold hover:bg-amber-400 disabled:opacity-50"
          >
            {downloading ? 'Preparing download…' : 'Download report (PDF)'}
          </button>
          <button
            type="button"
            onClick={handleRegenerate}
            disabled={downloading}
            className="px-6 py-3 rounded-lg border border-slate-300 text-slate-700 font-medium hover:bg-slate-50 disabled:opacity-50"
          >
            Regenerate report
          </button>
          <button
            type="button"
            onClick={handleStartNew}
            className="px-6 py-3 rounded-lg border border-slate-300 text-slate-700 font-medium hover:bg-slate-50"
          >
            Start new analysis
          </button>
        </div>
      </div>

      <p className="mt-6">
        <button
          type="button"
          onClick={() => navigate('/dashboard')}
          className="text-amber-600 font-medium hover:text-amber-700"
        >
          Back to dashboard
        </button>
      </p>
    </div>
  );
}
