/**
 * Map validation API response to human-readable summary (no raw JSON, no technical terms).
 */

export function getAcceptabilityLabel(status) {
  if (!status) return 'Not determined';
  const s = String(status).toUpperCase();
  if (s === 'ACCEPTABLE') return 'Acceptable';
  if (s === 'NOT ACCEPTABLE') return 'Not acceptable at this stage';
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
  const contractSummary = validationResult?.contract_summary || {};
  const programmeSummary = validationResult?.programme_summary || {};
  const pcm = alignment?.programme_compliance_model || {};
  const rawRequired = pcm.required_activities;
  const requiredActivities = Array.isArray(rawRequired) ? rawRequired : (rawRequired && typeof rawRequired === 'object' ? Object.values(rawRequired) : []);
  const failureReasons = Array.isArray(vs.acceptability_failure_reasons) ? vs.acceptability_failure_reasons : [];
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
  const failureReasons = Array.isArray(vs.acceptability_failure_reasons) ? vs.acceptability_failure_reasons : [];
  const recommendations = Array.isArray(validationResult?.recommendations) ? validationResult.recommendations : [];

  return {
    acceptabilityStatus: getAcceptabilityLabel(vs.acceptability_status),
    programmeDecisionText: vs.programme_decision_text || '',
    programmeDecisionDetail: vs.programme_decision_detail || '',
    qualitySummary: vs.quality_summary || '',
    failureReasons,
    requiredActions: recommendations,
    summaryExplanation: vs.summary_explanation || '',
  };
}
