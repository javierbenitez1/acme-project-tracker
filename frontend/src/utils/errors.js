const LABELS = {
  waiting_on: 'Waiting on',
  open_deliverables: 'Still open',
  open_milestones: 'Still open',
  dependents: 'Already started',
  milestones: 'Affected',
};

/** Turns an API error into one readable sentence, including any list of names the server sent back. */
export function describeError(error) {
  const parts = [error?.message || 'Something went wrong. Try again in a moment.'];
  const details = error?.details;
  if (details && typeof details === 'object') {
    Object.entries(details).forEach(([key, value]) => {
      if (Array.isArray(value) && value.length && typeof value[0] === 'string') {
        parts.push(`${LABELS[key] || key}: ${value.join(', ')}.`);
      }
    });
  }
  return parts.join(' ');
}