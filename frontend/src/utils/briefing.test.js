import { describe, expect, it } from 'vitest';
import { projectBriefing } from './briefing';

const kiosk = {
  name: 'Branch Kiosk Rollout', health: 'at_risk', status: 'active', is_archived: false,
  progress: 56, time_elapsed_pct: 86, days_remaining: 12, end_date: '2026-10-25',
  budget_planned: 180000, budget_spent: 120000, budget_used_pct: 67,
  risk_reasons: ['Behind schedule: 56% done with 86% of the time used'],
  date_changes: [{ changed_at: '2026-10-13T15:00:00Z', reason: 'Card reader shipment delayed by the vendor.' }],
};
const milestones = [
  { name: 'Site surveys', status: 'done', end_date: '2026-08-29', start_date: '2026-08-04', is_overdue: false },
  { name: 'Install at branches', status: 'in_progress', end_date: '2026-10-21', start_date: '2026-10-03', is_overdue: false },
  { name: 'Go-live review', status: 'not_started', start_date: '2026-10-21', end_date: '2026-10-25', is_overdue: false,
    blocked_by: [{ name: 'Install at branches' }] },
];

describe('projectBriefing', () => {
  const text = projectBriefing(kiosk, milestones);

  it('leads with health, progress and time', () => {
    expect(text).toMatch(/^Branch Kiosk Rollout is at risk\. It is 56% complete with 86% of its time used, and it ends Oct 25, in 12 days\./);
  });

  it('describes milestone progress and what comes next', () => {
    expect(text).toContain('1 of 3 milestones is done, and Install at branches is in progress (due Oct 21).');
    expect(text).toContain('Next up is Go-live review, starting Oct 21 once Install at branches is done.');
  });

  it('includes the budget, the latest schedule change and the risks', () => {
    expect(text).toContain('$120,000 of the $180,000 budget is spent (67%).');
    expect(text).toContain('Card reader shipment delayed by the vendor.');
    expect(text).toContain('Watch: behind schedule');
  });

  it('leaves budget numbers out for people who should not see them', () => {
    expect(projectBriefing(kiosk, milestones, { includeBudget: false })).not.toContain('$');
  });

  it('describes completed and archived projects without risks', () => {
    const done = projectBriefing({ ...kiosk, status: 'completed', is_archived: true, archived_at: '2026-10-01T10:00:00Z' }, []);
    expect(done).toMatch(/^Branch Kiosk Rollout is complete as of Oct 1\./);
    expect(done).not.toContain('Watch:');
    const archived = projectBriefing({ ...kiosk, is_archived: true, archive_reason: 'Folded into another program.' }, []);
    expect(archived).toMatch(/^Branch Kiosk Rollout is archived \(Folded into another program\)\./);
  });
});