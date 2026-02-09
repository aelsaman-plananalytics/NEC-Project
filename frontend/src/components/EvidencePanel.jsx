import React, { useState } from 'react';
import { ConfidenceBadge } from './ConfidenceLegend';

/**
 * Expandable evidence panel: summary by default, expand to see contract text, programme activities, reasoning.
 */
export default function EvidencePanel({
  title,
  summary,
  contractText,
  programmeActivities = [],
  reasoning,
  confidenceBand,
  defaultExpanded = false,
  className = '',
}) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const hasDetail = contractText || (programmeActivities && programmeActivities.length > 0) || reasoning;

  return (
    <div className={`border border-slate-200 rounded-lg overflow-hidden ${className}`}>
      <button
        type="button"
        onClick={() => hasDetail && setExpanded((e) => !e)}
        className={`w-full text-left px-4 py-3 flex items-center justify-between gap-2 transition-colors ${
          hasDetail ? 'hover:bg-slate-50' : 'cursor-default'
        }`}
        aria-expanded={expanded}
        disabled={!hasDetail}
      >
        <div className="min-w-0 flex-1">
          {title && <p className="font-medium text-slate-800 truncate">{title}</p>}
          <p className="text-sm text-slate-600 mt-0.5">{summary}</p>
        </div>
        {confidenceBand && (
          <span className="shrink-0">
            <ConfidenceBadge band={confidenceBand} showLabel={false} />
          </span>
        )}
        {hasDetail && (
          <span className="shrink-0 text-slate-400" aria-hidden>
            {expanded ? '▼' : '▶'}
          </span>
        )}
      </button>
      {expanded && hasDetail && (
        <div className="border-t border-slate-200 bg-slate-50/80 px-4 py-3 text-sm space-y-3">
          {contractText && (
            <div>
              <p className="font-medium text-slate-600 mb-1">Contract wording</p>
              <p className="text-slate-700 whitespace-pre-wrap">{contractText}</p>
            </div>
          )}
          {programmeActivities && programmeActivities.length > 0 && (
            <div>
              <p className="font-medium text-slate-600 mb-1">Programme activities</p>
              <ul className="list-disc pl-5 text-slate-700 space-y-0.5">
                {programmeActivities.map((act, i) => (
                  <li key={i}>{typeof act === 'string' ? act : act?.name || act?.text || '—'}</li>
                ))}
              </ul>
            </div>
          )}
          {reasoning && (
            <div>
              <p className="font-medium text-slate-600 mb-1">Reasoning</p>
              <p className="text-slate-700">{reasoning}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
