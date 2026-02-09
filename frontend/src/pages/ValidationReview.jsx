import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { usePipeline } from '../context/PipelineContext';
import { useAuth } from '../context/AuthContext';
import { buildValidationReport } from '../services/api';
import EvidencePanel from '../components/EvidencePanel';
import ConfidenceLegend from '../components/ConfidenceLegend';

export default function ValidationReview() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const {
    validationResult,
    proceedToReport,
    goToStage,
    userConfirmations,
    addUserConfirmation,
  } = usePipeline();
  const [builtReport, setBuiltReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [crossView, setCrossView] = useState(null);

  useEffect(() => {
    if (!validationResult) return;
    let cancelled = false;
    setLoading(true);
    setError('');
    const payload = { ...validationResult };
    if (userConfirmations && userConfirmations.length > 0) {
      payload.user_confirmations = userConfirmations.map((c) => ({
        finding_id: c.findingId,
        confirmed: c.confirmed,
        note: c.note,
        timestamp: c.timestamp,
      }));
    }
    buildValidationReport(payload)
      .then((data) => {
        if (!cancelled) setBuiltReport(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message || 'Could not load report preview.');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
  }, [validationResult, userConfirmations]);

  const sectionScopeForMemo = builtReport?.section_scope_contract_alignment;
  const sectionDForMemo = builtReport?.section_d_required_activities_and_gates;
  const scopeRowsForMemo = Array.isArray(sectionScopeForMemo?.scope_rows) ? sectionScopeForMemo.scope_rows : [];
  const requiredTableForMemo = Array.isArray(sectionDForMemo?.required_activities_table) ? sectionDForMemo.required_activities_table : [];

  const { activityToObligations, obligationToActivities } = useMemo(() => {
    const actToOb = new Map();
    const obToAct = new Map();
    scopeRowsForMemo.forEach((row) => {
      const ob = row.contract_scope || row.constraint;
      const acts = row.programme_activities || [];
      if (ob) {
        obToAct.set(ob, [...(obToAct.get(ob) || []), ...acts]);
        acts.forEach((a) => {
          const key = typeof a === 'string' ? a : a?.name || a;
          if (key) actToOb.set(key, [...(actToOb.get(key) || []), ob]);
        });
      }
    });
    requiredTableForMemo.forEach((row) => {
      const ob = row.contract_activity;
      const notes = row.notes || '';
      const match = notes.match(/Shown as:\s*([^.]+)/);
      const acts = match ? match[1].split(',').map((s) => s.trim()).filter(Boolean) : [];
      if (ob) {
        obToAct.set(ob, [...(obToAct.get(ob) || []), ...acts]);
        acts.forEach((a) => {
          actToOb.set(a, [...(actToOb.get(a) || []), ob]);
        });
      }
    });
    return { activityToObligations: actToOb, obligationToActivities: obToAct };
  }, [scopeRowsForMemo, requiredTableForMemo]);

  if (!validationResult) {
    navigate('/programme', { replace: true });
    return null;
  }

  const handleProceed = () => {
    proceedToReport();
    navigate('/results');
  };

  const handleBack = () => {
    goToStage(2);
    navigate('/programme');
  };

  if (loading) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-8">
        <h1 className="font-heading text-2xl font-bold text-slate-900 mb-2">Validation review</h1>
        <p className="text-slate-600">Building preview from the same data as your report…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-8">
        <h1 className="font-heading text-2xl font-bold text-slate-900 mb-2">Validation review</h1>
        <div className="p-4 rounded-lg bg-red-50 border border-red-200 text-red-800 mb-4">{error}</div>
        <button
          type="button"
          onClick={handleBack}
          className="px-6 py-3 rounded-lg border border-slate-300 text-slate-700 font-medium hover:bg-slate-50"
        >
          Go back to programme upload
        </button>
      </div>
    );
  }

  const sectionA = builtReport?.section_a_executive_summary || {};
  const sectionB = builtReport?.section_b_what_determined_outcome || {};
  const sectionD = builtReport?.section_d_required_activities_and_gates || {};
  const sectionScope = builtReport?.section_scope_contract_alignment || {};
  const sectionH = builtReport?.section_h_next_steps || {};
  const whatToReview = builtReport?.section_what_to_review_next || {};
  const requiredTable = Array.isArray(sectionD.required_activities_table) ? sectionD.required_activities_table : [];
  const scopeRows = Array.isArray(sectionScope.scope_rows) ? sectionScope.scope_rows : [];
  const constraintRows = Array.isArray(sectionScope.constraint_rows) ? sectionScope.constraint_rows : [];
  const nextSteps = Array.isArray(sectionH.next_steps) ? sectionH.next_steps : [];
  const whatToReviewItems = Array.isArray(whatToReview.items) ? whatToReview.items : [];

  const hasCrossViewData = activityToObligations.size > 0 || obligationToActivities.size > 0;

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <h1 className="font-heading text-2xl font-bold text-slate-900 mb-2">Validation review</h1>
      <p className="text-slate-600 mb-6">
        Below is a summary of how the programme compares to the contract. Expand any row for contract text, programme activities, and reasoning. Add notes if you want them included in the report.
      </p>

      <div className="space-y-6">
        <section className="bg-white border border-slate-200 rounded-xl p-6">
          <h2 className="font-semibold text-slate-800 mb-2">System assessment — Programme acceptability</h2>
          {sectionA.programme_stage_context && (
            <p className="text-slate-600 text-sm italic mb-2">{sectionA.programme_stage_context}</p>
          )}
          {sectionA.executive_summary_text ? (
            <p className="text-slate-700">{sectionA.executive_summary_text}</p>
          ) : (
            <>
              <p className="text-slate-700">
                <strong>{sectionA.decision_heading || 'Programme decision'}</strong>
                {sectionA.decision_detail && <> — {sectionA.decision_detail}</>}
              </p>
              {sectionA.quality_summary && (
                <p className="text-slate-600 text-sm mt-2">{sectionA.quality_summary}</p>
              )}
            </>
          )}
          {sectionB.alternative_interpretation && (
            <p className="text-slate-600 text-sm mt-3 italic">{sectionB.alternative_interpretation}</p>
          )}
        </section>

        {hasCrossViewData && (
          <section className="bg-white border border-slate-200 rounded-xl p-6">
            <h2 className="font-semibold text-slate-800 mb-2">Activity ↔ Obligation cross-view</h2>
            <p className="text-slate-600 text-sm mb-3">
              Click an activity to see which obligations it supports; click an obligation to see supporting activities.
            </p>
            {crossView ? (
              <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                <p className="font-medium text-slate-800 mb-2">{crossView.title}</p>
                <ul className="list-disc pl-5 text-slate-700 text-sm space-y-1">
                  {(crossView.items || []).map((item, i) => (
                    <li key={i}>{item}</li>
                  ))}
                </ul>
                <button
                  type="button"
                  onClick={() => setCrossView(null)}
                  className="mt-3 text-sm text-slate-600 hover:text-slate-800"
                >
                  Close
                </button>
              </div>
            ) : (
              <div className="flex flex-wrap gap-2">
                {[...obligationToActivities.keys()].slice(0, 12).map((ob) => (
                  <button
                    key={ob}
                    type="button"
                    onClick={() =>
                      setCrossView({
                        title: `Obligation: ${ob.slice(0, 50)}${ob.length > 50 ? '…' : ''}`,
                        items: obligationToActivities.get(ob) || [],
                      })
                    }
                    className="px-3 py-1.5 rounded-md bg-slate-100 text-slate-700 text-sm hover:bg-slate-200 truncate max-w-[200px]"
                    title={ob}
                  >
                    {ob.slice(0, 35)}…
                  </button>
                ))}
                {[...activityToObligations.keys()].slice(0, 8).map((act) => (
                  <button
                    key={act}
                    type="button"
                    onClick={() =>
                      setCrossView({
                        title: `Activity: ${act.slice(0, 50)}${act.length > 50 ? '…' : ''}`,
                        items: activityToObligations.get(act) || [],
                      })
                    }
                    className="px-3 py-1.5 rounded-md bg-amber-50 text-slate-700 text-sm hover:bg-amber-100 truncate max-w-[200px]"
                    title={act}
                  >
                    {act.slice(0, 35)}…
                  </button>
                ))}
              </div>
            )}
          </section>
        )}

        <section className="bg-white border border-slate-200 rounded-xl p-6">
          <h2 className="font-semibold text-slate-800 mb-2">System assessment — Required activities</h2>
          {sectionD.required_summary && (
            <p className="text-slate-600 text-sm mb-3">{sectionD.required_summary}</p>
          )}
          <ConfidenceLegend className="mb-3" />
          {requiredTable.length > 0 ? (
            <div className="space-y-2">
              {requiredTable.slice(0, 12).map((row, i) => {
                const findingId = `req-${i}-${(row.contract_activity || '').slice(0, 30)}`;
                const conf = userConfirmations.find((c) => c.findingId === findingId);
                return (
                  <div key={i} className="flex flex-col gap-1">
                    <EvidencePanel
                      title={row.contract_activity || '—'}
                      summary={`${row.when_required || ''} — ${row.shown_in_programme || ''}. ${row.notes || ''}`}
                      reasoning={row.notes}
                      confidenceBand={row.confidence_band}
                    />
                    <div className="flex items-center gap-2 pl-2 text-xs">
                      <span className="text-slate-500">Your note (optional, included in report):</span>
                      <input
                        type="text"
                        placeholder="Add a note…"
                        defaultValue={conf?.note}
                        onBlur={(e) => {
                          const v = e.target.value.trim();
                          if (v || conf) addUserConfirmation(findingId, { confirmed: true, note: v });
                        }}
                        className="flex-1 max-w-xs rounded border border-slate-200 px-2 py-1 text-slate-700"
                      />
                    </div>
                  </div>
                );
              })}
              {requiredTable.length > 12 && (
                <p className="text-slate-500 text-sm">… and {requiredTable.length - 12} more in the full report.</p>
              )}
            </div>
          ) : (
            <p className="text-slate-600 text-sm">{sectionD.summary || 'No required activities table in this report.'}</p>
          )}
        </section>

        <section className="bg-white border border-slate-200 rounded-xl p-6">
          <h2 className="font-semibold text-slate-800 mb-2">System assessment — Scope and constraints</h2>
          {sectionScope.section_intro && (
            <p className="text-slate-600 text-sm mb-2">{sectionScope.section_intro}</p>
          )}
          <ConfidenceLegend className="mb-3" />
          <p className="text-slate-600 text-sm mb-3">
            {scopeRows.length} scope item(s) and {constraintRows.length} constraint(s) were checked. Expand a row for contract wording and programme evidence.
          </p>
          <div className="space-y-2">
            {scopeRows.slice(0, 10).map((row, i) => (
              <EvidencePanel
                key={i}
                title={(row.contract_scope || '').slice(0, 60) + (row.contract_scope?.length > 60 ? '…' : '')}
                summary={row.representation_status || row.notes || '—'}
                contractText={row.contract_scope}
                programmeActivities={row.programme_activities || []}
                reasoning={row.notes}
                confidenceBand={row.confidence_band}
              />
            ))}
            {constraintRows.slice(0, 5).map((row, i) => (
              <EvidencePanel
                key={`c-${i}`}
                title={(row.constraint || '').slice(0, 60) + (row.constraint?.length > 60 ? '…' : '')}
                summary={`${row.handling || ''} — ${row.programme_evidence || '—'}`}
                contractText={row.constraint}
                programmeActivities={row.programme_evidence ? [row.programme_evidence] : []}
                reasoning={row.handling}
                confidenceBand={row.confidence_band}
              />
            ))}
          </div>
          {sectionScope.acceptability_clarification && (
            <p className="text-slate-600 text-sm mt-3 font-medium">{sectionScope.acceptability_clarification}</p>
          )}
        </section>

        {whatToReviewItems.length > 0 && (
          <section className="bg-white border border-slate-200 rounded-xl p-6">
            <h2 className="font-semibold text-slate-800 mb-2">What to review next</h2>
            {whatToReview.section_intro && (
              <p className="text-slate-600 text-sm mb-2">{whatToReview.section_intro}</p>
            )}
            <ul className="list-disc pl-6 text-slate-700 text-sm space-y-1">
              {whatToReviewItems.slice(0, 5).map((item, i) => (
                <li key={i}>{item}</li>
              ))}
            </ul>
          </section>
        )}

        {nextSteps.length > 0 && (
          <section className="bg-slate-50 border border-slate-200 rounded-xl p-6">
            <h2 className="font-semibold text-slate-800 mb-2">Next steps</h2>
            <ul className="list-disc pl-6 text-slate-700 text-sm space-y-1">
              {nextSteps.slice(0, 5).map((step, i) => (
                <li key={i}>{step}</li>
              ))}
              {nextSteps.length > 5 && (
                <li className="text-slate-500">… and {nextSteps.length - 5} more (in full report)</li>
              )}
            </ul>
          </section>
        )}

        {userConfirmations.length > 0 && (
          <section className="bg-amber-50/50 border border-amber-200 rounded-xl p-6">
            <h2 className="font-semibold text-slate-800 mb-2">Professional judgement — Your confirmations and notes</h2>
            <p className="text-slate-600 text-sm mb-2">
              These notes will appear in the report, clearly separated from the system assessment.
            </p>
            <ul className="list-disc pl-6 text-slate-700 text-sm space-y-1">
              {userConfirmations.filter((c) => c.note).map((c, i) => (
                <li key={i}>
                  <span className="text-slate-500">{new Date(c.timestamp).toLocaleString()}</span>
                  {c.note && ` — ${c.note}`}
                </li>
              ))}
            </ul>
          </section>
        )}

        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            onClick={handleProceed}
            className="px-6 py-3 rounded-lg bg-amber-500 text-slate-900 font-semibold hover:bg-amber-400"
          >
            Proceed to final report
          </button>
          <button
            type="button"
            onClick={handleBack}
            className="px-6 py-3 rounded-lg border border-slate-300 text-slate-700 font-medium hover:bg-slate-50"
          >
            Go back to programme upload
          </button>
        </div>
      </div>
      <p className="mt-4 text-sm text-slate-500">Review — Next: download your Programme Validation report.</p>
    </div>
  );
}
