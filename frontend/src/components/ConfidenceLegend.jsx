import React from 'react';

/** Muted confidence band legend. Descriptive only; does not affect outcomes. */
export default function ConfidenceLegend({ className = '' }) {
  return (
    <div className={`flex flex-wrap items-center gap-4 text-xs text-slate-500 ${className}`}>
      <span className="font-medium text-slate-600">Confidence:</span>
      <span className="flex items-center gap-1.5">
        <span className="h-2 w-2 rounded-full bg-emerald-400/80" aria-hidden />
        High confidence
      </span>
      <span className="flex items-center gap-1.5">
        <span className="h-2 w-2 rounded-full bg-amber-400/70" aria-hidden />
        Moderate confidence
      </span>
      <span className="flex items-center gap-1.5">
        <span className="h-2 w-2 rounded-full bg-slate-400/70" aria-hidden />
        Judgement required
      </span>
      <span className="italic">Descriptive only; does not change the acceptability outcome.</span>
    </div>
  );
}

/** Return a small confidence indicator element for a band value. */
export function ConfidenceBadge({ band, showLabel = true }) {
  if (!band) return null;
  const b = String(band).toLowerCase();
  const isHigh = b.includes('high');
  const isModerate = b.includes('moderate');
  const isJudgement = b.includes('judgement');
  const dotClass = isHigh
    ? 'bg-emerald-400/80'
    : isModerate
      ? 'bg-amber-400/70'
      : isJudgement
        ? 'bg-slate-400/70'
        : 'bg-slate-300/70';
  return (
    <span className="inline-flex items-center gap-1 text-slate-500 text-xs">
      <span className={`h-1.5 w-1.5 rounded-full shrink-0 ${dotClass}`} aria-hidden />
      {showLabel && <span>{band}</span>}
    </span>
  );
}
