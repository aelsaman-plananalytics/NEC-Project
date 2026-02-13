/**
 * Run status display: badge label and CSS classes.
 * Backend status: processing | completed | failed | timed_out
 */

export function getRunStatusDisplay(status, acceptabilityStatus) {
  const s = (status || 'completed').toLowerCase();
  if (s === 'processing') {
    return { label: 'Processing', className: 'bg-blue-100 text-blue-800' };
  }
  if (s === 'failed' || s === 'timed_out') {
    return { label: s === 'timed_out' ? 'Timed out' : 'Failed', className: 'bg-red-100 text-red-800' };
  }
  // completed: green if acceptable, amber if not
  const acc = (acceptabilityStatus || '').toUpperCase();
  if (acc === 'ACCEPTABLE') {
    return { label: 'Acceptable at this stage', className: 'bg-green-100 text-green-800' };
  }
  if (acc === 'NOT_ACCEPTABLE' || acc === 'NOT ACCEPTABLE') {
    return { label: 'Not acceptable at this stage', className: 'bg-amber-100 text-amber-800' };
  }
  return { label: 'Completed', className: 'bg-slate-100 text-slate-700' };
}
