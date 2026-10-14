import { formatDate } from './format';

/** Color for the critical path on charts. Purple so it never reads as overdue (red) or in progress (amber). */
export const CRITICAL_COLOR = '#8B4FD0';

const days = (count) => `${count} ${Math.abs(count) === 1 ? 'day' : 'days'}`;

/** One sentence about how much delay the project can absorb before its end date has to move. */
export function bufferText(schedule) {
  if (!schedule || schedule.buffer_days === null || schedule.buffer_days === undefined) {
    return 'Every milestone is done, so there is no critical path left.';
  }
  if (schedule.buffer_days <= 0) {
    return 'There is no buffer: any delay on these milestones pushes back the project end date.';
  }
  return `These milestones can slip ${days(schedule.buffer_days)} in total before the project end date has to move.`;
}

/** The buffer as a short phrase, for example "9 days of buffer". */
export function bufferPhrase(bufferDays) {
  if (bufferDays === null || bufferDays === undefined) return '';
  return bufferDays <= 0 ? 'no buffer left' : `${days(bufferDays)} of buffer`;
}

/** How much one milestone can slip, as a short label. */
export function slackText(slackDays) {
  if (slackDays === null || slackDays === undefined) return '';
  return slackDays <= 0 ? 'No slack' : `Can slip ${days(slackDays)}`;
}

/** The delivery forecast as a sentence, plus how serious it is (for the alert color). */
export function forecastSummary(forecast) {
  if (!forecast) return null;
  const when = forecast.projected_end ? formatDate(forecast.projected_end) : '';
  switch (forecast.status) {
    case 'late':
      return { severity: 'warning', text: `At the current pace this project finishes around ${when}, ${days(forecast.days_late)} after its end date.` };
    case 'early':
      return { severity: 'success', text: `At the current pace this project finishes around ${when}, ${days(-forecast.days_late)} ahead of its end date.` };
    case 'on_time':
      return { severity: 'success', text: `At the current pace this project finishes around ${when}, on schedule.` };
    case 'not_enough_data':
      return { severity: 'info', text: 'There is not enough progress yet to forecast a finish date.' };
    case 'complete':
      return { severity: 'success', text: 'All the work is done.' };
    default:
      return null;
  }
}
