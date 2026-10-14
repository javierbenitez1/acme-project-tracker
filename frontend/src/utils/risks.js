/** Shared risk register vocabulary: scales, labels and colors, so every screen describes risks the same way. */
export const LIKELIHOOD = ['Rare', 'Unlikely', 'Possible', 'Likely', 'Almost certain'];
export const IMPACT = ['Minimal', 'Minor', 'Moderate', 'Major', 'Severe'];
export const CATEGORIES = [
  ['schedule', 'Schedule'], ['budget', 'Budget'], ['resources', 'People'], ['vendor', 'Vendor'],
  ['technical', 'Technical'], ['scope', 'Scope'], ['other', 'Other'],
];
export const STATUS_LABELS = { open: 'Open', mitigating: 'Mitigating', closed: 'Closed', occurred: 'Happened' };
export const LEVELS = {
  high: { label: 'High', color: '#C2412D' },
  medium: { label: 'Medium', color: '#C98A12' },
  low: { label: 'Low', color: '#2F8F5B' },
};
export const ACTIVE_STATUSES = ['open', 'mitigating'];

/** Same bands as the server: 15 to 25 high, 8 to 14 medium, 1 to 7 low. */
export function riskLevel(score) {
  if (score >= 15) return 'high';
  if (score >= 8) return 'medium';
  return 'low';
}

export const categoryLabel = (value) => (CATEGORIES.find(([key]) => key === value) || [value, value])[1];

const count = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`;

/** One sentence summing up the register, for the top of the Risks tab. */
export function registerSummary(summary) {
  if (!summary || !summary.active) return 'No active risks right now.';
  const parts = ['high', 'medium', 'low'].filter((key) => summary[key]).map((key) => `${summary[key]} ${key}`);
  let text = `${count(summary.active, 'active risk')}: ${parts.join(', ')}.`;
  if (summary.reviews_overdue) {
    text += ` ${count(summary.reviews_overdue, 'review')} ${summary.reviews_overdue === 1 ? 'is' : 'are'} overdue.`;
  }
  return text;
}

/** The 5x5 matrix: rows from impact 5 (top) to 1, columns from likelihood 1 to 5, with the risks in each cell. */
export function matrixCells(risks) {
  return [5, 4, 3, 2, 1].map((impact) => [1, 2, 3, 4, 5].map((likelihood) => ({
    impact,
    likelihood,
    level: riskLevel(impact * likelihood),
    risks: risks.filter((r) => r.impact === impact && r.likelihood === likelihood),
  })));
}