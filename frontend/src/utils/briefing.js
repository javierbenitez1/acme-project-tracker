import { health } from '../theme';
import { formatDate, formatMoney } from './format';

const plural = (count, word) => `${count} ${word}${count === 1 ? '' : 's'}`;
const joinList = (items) => (items.length <= 1 ? items.join('') : `${items.slice(0, -1).join(', ')} and ${items[items.length - 1]}`);
const lowerFirst = (text) => text.charAt(0).toLowerCase() + text.slice(1);
const trimPeriod = (text) => text.replace(/\.$/, '');

function schedulePhrase(project) {
  const days = project.days_remaining;
  if (days > 1) return `ends ${formatDate(project.end_date)}, in ${days} days`;
  if (days === 1) return 'ends tomorrow';
  if (days === 0) return 'ends today';
  return `was due ${formatDate(project.end_date)}, ${plural(-days, 'day')} ago`;
}

/** A plain-English status update built from live project data, ready to paste into an email or chat. */
export function projectBriefing(project, milestones = [], { includeBudget = true } = {}) {
  const sentences = [];
  if (project.status === 'completed') {
    sentences.push(`${project.name} is complete${project.archived_at ? ` as of ${formatDate(project.archived_at)}` : ''}.`);
  } else if (project.is_archived) {
    sentences.push(`${project.name} is archived${project.archive_reason ? ` (${trimPeriod(project.archive_reason)})` : ''}.`);
  } else {
    const label = (health[project.health]?.label || project.health).toLowerCase();
    sentences.push(`${project.name} is ${label}. It is ${project.progress}% complete with `
      + `${project.time_elapsed_pct}% of its time used, and it ${schedulePhrase(project)}.`);
  }

  if (milestones.length) {
    const done = milestones.filter((m) => m.status === 'done').length;
    const current = milestones.filter((m) => m.status === 'in_progress');
    let text = `${done} of ${plural(milestones.length, 'milestone')} ${done === 1 ? 'is' : 'are'} done`;
    if (current.length) {
      text += `, and ${joinList(current.map((m) => `${m.name} is in progress (due ${formatDate(m.end_date)})`))}`;
    }
    sentences.push(`${text}.`);
    const overdue = milestones.filter((m) => m.is_overdue);
    if (overdue.length) {
      sentences.push(`Overdue: ${joinList(overdue.map((m) => `${m.name}, due ${formatDate(m.end_date)}`))}.`);
    }
    const next = milestones
      .filter((m) => m.status === 'not_started')
      .sort((a, b) => a.start_date.localeCompare(b.start_date))[0];
    if (next && !project.is_archived) {
      const waiting = next.blocked_by?.length
        ? ` once ${joinList(next.blocked_by.map((b) => b.name))} ${next.blocked_by.length === 1 ? 'is' : 'are'} done`
        : '';
      sentences.push(`Next up is ${next.name}, starting ${formatDate(next.start_date)}${waiting}.`);
    }
  }

  if (includeBudget && Number(project.budget_planned) > 0) {
    sentences.push(`${formatMoney(project.budget_spent)} of the ${formatMoney(project.budget_planned)} budget `
      + `is spent (${project.budget_used_pct}%).`);
  }
  const latest = project.date_changes?.[0];
  if (latest) sentences.push(`The schedule last changed on ${formatDate(latest.changed_at)}: ${trimPeriod(latest.reason)}.`);
  if (!project.is_archived && project.risk_reasons?.length) {
    sentences.push(`Watch: ${joinList(project.risk_reasons.map(lowerFirst))}.`);
  }
  return sentences.join(' ');
}