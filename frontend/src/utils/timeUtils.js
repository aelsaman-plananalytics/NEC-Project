/**
 * Humanized relative time (e.g. "5 minutes ago", "2 days ago").
 * @param {string|number|Date} date - ISO string, timestamp, or Date
 * @returns {string}
 */
export function humanizeTime(date) {
  if (date == null) return '';
  const d = typeof date === 'object' && date instanceof Date ? date : new Date(date);
  if (Number.isNaN(d.getTime())) return '';
  const now = new Date();
  const diffMs = now - d;
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHour = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHour / 24);

  if (diffSec < 60) return 'Just now';
  if (diffMin < 60) return diffMin === 1 ? '1 minute ago' : `${diffMin} minutes ago`;
  if (diffHour < 24) return diffHour === 1 ? '1 hour ago' : `${diffHour} hours ago`;
  if (diffDay < 7) return diffDay === 1 ? '1 day ago' : `${diffDay} days ago`;
  if (diffDay < 30) {
    const weeks = Math.floor(diffDay / 7);
    return weeks === 1 ? '1 week ago' : `${weeks} weeks ago`;
  }
  return d.toLocaleDateString();
}
