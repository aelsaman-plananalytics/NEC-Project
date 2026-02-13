/**
 * Map validation API response to human-readable summary (no raw JSON, no technical terms).
 */

/** Normalise item for display: string → string; object → text ?? message ?? reason ?? "—"; never String(object). */
export function normaliseText(item) {
  if (item == null) return '—';
  if (typeof item === 'string') return item.trim() || '—';
  if (typeof item === 'object') {
    const s = item.text ?? item.message ?? item.reason ?? null;
    return s != null ? String(s).trim() || '—' : '—';
  }
  return '—';
}

/** Humanize backend acceptability; never show raw enum. */
export function getAcceptabilityLabel(status) {
  if (!status) return 'Not determined';
  const s = String(status).toUpperCase();
  if (s === 'ACCEPTABLE') return 'Acceptable at this stage';
  if (s === 'NOT ACCEPTABLE' || s === 'NOT_ACCEPTABLE') return 'Not acceptable at this stage';
  return status;
}

export function getOverallStatusLabel(status) {
  if (!status) return '—';
  const s = String(status).toLowerCase();
  if (s === 'pass') return 'Pass';
  if (s === 'fail') return 'Fail';
  if (s === 'needs_attention') return 'Needs attention';
  return status;
}

export function buildValidationPreview(validationResult) {
  const vs = validationResult?.validation_summary || {};
  const alignment = validationResult?.alignment || {};
  const pcm = alignment?.programme_compliance_model || {};
  const rawRequired = pcm.required_activities;
  const requiredActivities = Array.isArray(rawRequired) ? rawRequired : (rawRequired && typeof rawRequired === 'object' ? Object.values(rawRequired) : []);
  const rawFailureReasons = Array.isArray(vs.acceptability_failure_reasons) ? vs.acceptability_failure_reasons : [];
  const failureReasons = rawFailureReasons.map(normaliseText);
  const decisionText = vs.programme_decision_text || vs.programme_decision_detail || '';
  const decisionDetail = vs.programme_decision_detail || '';

  const scopeAlignment = alignment?.scope_contract_alignment || {};
  const scopeEvidence = Array.isArray(scopeAlignment?.scope_evidence_rows) ? scopeAlignment.scope_evidence_rows : [];
  const constraintRows = Array.isArray(scopeAlignment?.constraint_coverage_rows) ? scopeAlignment.constraint_coverage_rows : [];

  return {
    acceptabilityStatus: getAcceptabilityLabel(vs.acceptability_status),
    overallStatus: getOverallStatusLabel(vs.overall_status),
    programmeDecisionText: decisionText,
    programmeDecisionDetail: decisionDetail,
    acceptabilityScore: vs.acceptability_score ?? 0,
    failureReasons,
    requiredActivitiesCount: requiredActivities.length,
    requiredActivities: requiredActivities.slice(0, 20).map((a) => ({
      text: typeof a === 'string' ? a : (a?.text || a?.name || a?.description || '—'),
      whenRequired: typeof a === 'object' && a?.when_required ? a.when_required : '—',
    })),
    scopeEvidenceCount: scopeEvidence.length,
    constraintCoverageCount: constraintRows.length,
    qualitySummary: vs.quality_summary || '',
  };
}

export function buildResultsForReport(validationResult) {
  const vs = validationResult?.validation_summary || {};
  const rawFailureReasons = Array.isArray(vs.acceptability_failure_reasons) ? vs.acceptability_failure_reasons : [];
  const rawRecommendations = Array.isArray(validationResult?.recommendations) ? validationResult.recommendations : [];
  const failureReasons = rawFailureReasons.map(normaliseText);
  const requiredActions = rawRecommendations.map(normaliseText);

  return {
    acceptabilityStatus: getAcceptabilityLabel(vs.acceptability_status),
    programmeDecisionText: vs.programme_decision_text || '',
    programmeDecisionDetail: vs.programme_decision_detail || '',
    qualitySummary: vs.quality_summary || '',
    failureReasons,
    requiredActions,
    summaryExplanation: vs.summary_explanation || '',
  };
}
