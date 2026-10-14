const currency = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });
const compactCurrency = new Intl.NumberFormat('en-US', {
  style: 'currency', currency: 'USD', notation: 'compact', maximumFractionDigits: 1,
});
const relative = new Intl.RelativeTimeFormat('en-US', { numeric: 'auto' });

export const formatMoney = (value, { compact = false } = {}) => (compact ? compactCurrency : currency).format(Number(value) || 0);

/** Dates from the API are YYYY-MM-DD. Parse them as local dates so they never shift by a day. */
export function parseDate(value) {
  if (!value) return null;
  if (value instanceof Date) return value;
  const [year, month, day] = String(value).slice(0, 10).split('-').map(Number);
  return new Date(year, month - 1, day);
}

export function today() {
  const now = new Date();
  return new Date(now.getFullYear(), now.getMonth(), now.getDate());
}

export const daysBetween = (from, to) => Math.round((parseDate(to) - parseDate(from)) / 86_400_000);

export function formatDate(value) {
  const date = parseDate(value);
  if (!date) return '';
  const options = { month: 'short', day: 'numeric' };
  if (date.getFullYear() !== new Date().getFullYear()) options.year = 'numeric';
  return date.toLocaleDateString('en-US', options);
}

export function formatDue(value) {
  const days = daysBetween(today(), value);
  if (days === 0) return 'Due today';
  if (days === 1) return 'Due tomorrow';
  if (days < 0) return `${Math.abs(days)} day${days === -1 ? '' : 's'} overdue`;
  return `Due in ${days} days`;
}

export function timeAgo(value) {
  const seconds = Math.round((new Date(value).getTime() - Date.now()) / 1000);
  const units = [['year', 31_536_000], ['month', 2_592_000], ['week', 604_800], ['day', 86_400], ['hour', 3_600], ['minute', 60]];
  for (const [unit, size] of units) {
    if (Math.abs(seconds) >= size) return relative.format(Math.round(seconds / size), unit);
  }
  return 'just now';
}

export const initials = (name = '') =>
  name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0].toUpperCase()).join('');
export const toIsoDate = (date) =>
  `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
