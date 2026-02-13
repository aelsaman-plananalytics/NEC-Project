import React, { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { usePipeline } from '../context/PipelineContext';
import { validateProgramme, apiGetLatestContractAnalysis } from '../services/api';
import { getAcceptabilityLabel } from '../utils/validationSummary';

export default function ProgrammeCompare() {
  const navigate = useNavigate();
  const { contractAnalysis, contractFile, setContractAnalysis } = usePipeline();
  const [fileA, setFileA] = useState(null);
  const [fileB, setFileB] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [resultA, setResultA] = useState(null);
  const [resultB, setResultB] = useState(null);
  const [loadingLatest, setLoadingLatest] = useState(false);
  const [latestMessage, setLatestMessage] = useState('');

  const runComparison = useCallback(async () => {
    if (!contractAnalysis || !fileA || !fileB) {
      setError('Please upload both programme files.');
      return;
    }
    setLoading(true);
    setError('');
    setResultA(null);
    setResultB(null);
    try {
      const [resA, resB] = await Promise.all([
        validateProgramme(fileA, contractAnalysis),
        validateProgramme(fileB, contractAnalysis),
      ]);
      setResultA(resA);
      setResultB(resB);
    } catch (err) {
      setError(err.message || 'Validation failed for one or both programmes.');
    } finally {
      setLoading(false);
    }
  }, [contractAnalysis, fileA, fileB]);

  const useLatestFromServer = useCallback(async () => {
    setLoadingLatest(true);
    setLatestMessage('');
    setError('');
    try {
      const data = await apiGetLatestContractAnalysis();
      const name = data?.project || data?.metadata?.filename || 'contract';
      setContractAnalysis(data, { name: name.replace(/\.[^.]+$/, '') + '.pdf', size: null });
      const n = (data?.programme_compliance_model?.required_activities || []).length;
      setLatestMessage(`Updated to server's latest analysis (${n} required activities). Click "Compare programmes" again.`);
      setResultA(null);
      setResultB(null);
    } catch (err) {
      setError(err.message || 'Could not load latest analysis from server.');
    } finally {
      setLoadingLatest(false);
    }
  }, [setContractAnalysis]);

  if (!contractAnalysis) {
    navigate('/analysis', { replace: true });
    return null;
  }

  const vsA = resultA?.validation_summary || {};
  const vsB = resultB?.validation_summary || {};
  const pcmA = resultA?.alignment?.programme_compliance_model?.required_activities || {};
  const pcmB = resultB?.alignment?.programme_compliance_model?.required_activities || {};
  const totalContractA = pcmA.total_contract_required_activities ?? pcmA.expected_now_total ?? 0;
  const totalContractB = pcmB.total_contract_required_activities ?? pcmB.expected_now_total ?? 0;
  const expectedNowA = pcmA.expected_now_total ?? 0;
  const expectedNowB = pcmB.expected_now_total ?? 0;
  const foundNowA = pcmA.expected_now_found ?? pcmA.matched_required_activities ?? 0;
  const foundNowB = pcmB.expected_now_found ?? pcmB.matched_required_activities ?? 0;
  const laterTotalA = pcmA.expected_later_total ?? 0;
  const laterTotalB = pcmB.expected_later_total ?? 0;
  const laterFoundA = pcmA.expected_later_found ?? 0;
  const laterFoundB = pcmB.expected_later_found ?? 0;
  const contractRequiredCount = (contractAnalysis?.programme_compliance_model?.required_activities || []).length;

  function formatRequiredActivities(nowTotal, nowFound, laterTotal, laterFound, totalContract) {
    if (totalContract === 0) return '0/0 (none specified in contract)';
    if (nowTotal > 0) return `${nowFound}/${nowTotal} expected now found`;
    if (laterTotal > 0) return `${laterFound}/${laterTotal} contract activities found (0 expected now, ${laterTotal} later)`;
    return `${nowFound}/${nowTotal} found`;
  }
  const requiredLabelA = formatRequiredActivities(expectedNowA, foundNowA, laterTotalA, laterFoundA, totalContractA);
  const requiredLabelB = formatRequiredActivities(expectedNowB, foundNowB, laterTotalB, laterFoundB, totalContractB);

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <h1 className="font-heading text-2xl font-bold text-slate-900 mb-2">Compare two programmes</h1>
      <p className="text-slate-600 mb-6">
        Same contract ({contractFile?.name || 'your contract'}), two programmes. Upload both XER files to see a side-by-side alignment summary. This does not change your current analysis.
      </p>

      <p className="text-sm text-slate-500 mb-4">
        Contract in this view: <strong>{contractRequiredCount}</strong> required activities
        {contractRequiredCount === 0 && (
          <span className="block mt-2 text-amber-700">
            If your contract has required activities and the main flow showed them, use the server&apos;s latest analysis below.
          </span>
        )}
      </p>

      {latestMessage && (
        <div className="mb-4 p-3 rounded-lg bg-green-50 border border-green-200 text-green-800 text-sm">{latestMessage}</div>
      )}

      {contractRequiredCount === 0 && (
        <div className="mb-4 p-3 rounded-lg bg-slate-50 border border-slate-200">
          <p className="text-sm text-slate-700 mb-2">Use the contract analysis last saved on the server (e.g. from when you ran &quot;Analyse contract&quot;) so required activities are included.</p>
          <button
            type="button"
            onClick={useLatestFromServer}
            disabled={loadingLatest}
            className="px-4 py-2 rounded-lg border border-slate-300 text-slate-700 text-sm font-medium hover:bg-slate-100 disabled:opacity-50"
          >
            {loadingLatest ? 'Loading…' : 'Use latest contract analysis from server'}
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
        <div className="bg-white border border-slate-200 rounded-xl p-4">
          <h3 className="font-semibold text-slate-800 mb-2">Programme A</h3>
          <input
            type="file"
            accept=".xer"
            onChange={(e) => {
              const f = e.target?.files?.[0];
              setFileA(f || null);
              setResultA(null);
              setResultB(null);
            }}
            className="block w-full text-sm text-slate-600 file:mr-3 file:py-2 file:px-3 file:rounded file:border-0 file:bg-amber-50 file:text-amber-900 file:font-medium"
          />
          {fileA && <p className="mt-2 text-sm text-slate-500">{fileA.name}</p>}
        </div>
        <div className="bg-white border border-slate-200 rounded-xl p-4">
          <h3 className="font-semibold text-slate-800 mb-2">Programme B</h3>
          <input
            type="file"
            accept=".xer"
            onChange={(e) => {
              const f = e.target?.files?.[0];
              setFileB(f || null);
              setResultA(null);
              setResultB(null);
            }}
            className="block w-full text-sm text-slate-600 file:mr-3 file:py-2 file:px-3 file:rounded file:border-0 file:bg-amber-50 file:text-amber-900 file:font-medium"
          />
          {fileB && <p className="mt-2 text-sm text-slate-500">{fileB.name}</p>}
        </div>
      </div>

      {error && (
        <div className="mb-4 p-3 rounded-lg bg-red-50 border border-red-200 text-red-800 text-sm">{error}</div>
      )}

      <button
        type="button"
        onClick={runComparison}
        disabled={!fileA || !fileB || loading}
        className="px-6 py-3 rounded-lg bg-amber-500 text-slate-900 font-semibold hover:bg-amber-400 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {loading ? 'Comparing…' : 'Compare programmes'}
      </button>

      {(resultA || resultB) && !loading && (
        <>
          {contractRequiredCount === 0 && (
            <p className="mt-6 p-3 rounded-lg bg-amber-50 border border-amber-200 text-amber-900 text-sm">
              No required activities were extracted from the contract for this run, so the validator did not check programmes against a list of contract activities. Acceptability is still based on scope, constraints, and other checks. Re-run contract analysis if you expect the contract to specify programme-required activities.
            </p>
          )}
          <div className="mt-8 grid grid-cols-1 md:grid-cols-2 gap-6 border-t border-slate-200 pt-8">
            <div className="bg-white border border-slate-200 rounded-xl p-6">
              <h3 className="font-semibold text-slate-800 mb-3">Programme A — {fileA?.name || '—'}</h3>
              {resultA ? (
                <ul className="space-y-2 text-sm text-slate-700">
                  <li>
                    <strong>Acceptability:</strong>{' '}
                    {getAcceptabilityLabel(vsA.acceptability_status)}
                  </li>
                  <li>
                    <strong>Required activities:</strong> {requiredLabelA}
                  </li>
                  {vsA.programme_decision_text && (
                    <li className="mt-2 text-slate-600">{vsA.programme_decision_text}</li>
                  )}
                </ul>
              ) : (
                <p className="text-slate-500">—</p>
              )}
            </div>
            <div className="bg-white border border-slate-200 rounded-xl p-6">
              <h3 className="font-semibold text-slate-800 mb-3">Programme B — {fileB?.name || '—'}</h3>
              {resultB ? (
                <ul className="space-y-2 text-sm text-slate-700">
                  <li>
                    <strong>Acceptability:</strong>{' '}
                    {getAcceptabilityLabel(vsB.acceptability_status)}
                    {(vsB.acceptability_status || '').toUpperCase() !== 'ACCEPTABLE' && (
                      <span className="block text-amber-700 text-xs mt-1">This programme does not meet the contract requirements.</span>
                    )}
                  </li>
                  <li>
                    <strong>Required activities:</strong> {requiredLabelB}
                  </li>
                  {vsB.programme_decision_text && (
                    <li className="mt-2 text-slate-600">{vsB.programme_decision_text}</li>
                  )}
                </ul>
              ) : (
                <p className="text-slate-500">—</p>
              )}
            </div>
          </div>
        </>
      )}

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
