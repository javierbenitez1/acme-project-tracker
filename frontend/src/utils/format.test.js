import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { daysBetween, formatDate, formatDue, formatMoney, initials, parseDate, toIsoDate } from './format';

describe('date helpers', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 5, 10, 15, 30));
  });
  afterEach(() => vi.useRealTimers());

  it('parses API dates as local dates so they never shift by a day', () => {
    const date = parseDate('2026-06-01');
    expect([date.getFullYear(), date.getMonth(), date.getDate()]).toEqual([2026, 5, 1]);
    expect(toIsoDate(date)).toBe('2026-06-01');
  });

  it('formats dates, adding the year only when it is not this year', () => {
    expect(formatDate('2026-06-01')).toBe('Jun 1');
    expect(formatDate('2025-12-24')).toBe('Dec 24, 2025');
    expect(formatDate(null)).toBe('');
  });

  it('describes due dates in plain words', () => {
    expect(formatDue('2026-06-10')).toBe('Due today');
    expect(formatDue('2026-06-11')).toBe('Due tomorrow');
    expect(formatDue('2026-06-15')).toBe('Due in 5 days');
    expect(formatDue('2026-06-09')).toBe('1 day overdue');
    expect(formatDue('2026-06-07')).toBe('3 days overdue');
    expect(daysBetween('2026-06-01', '2026-06-10')).toBe(9);
  });
});

describe('formatMoney and initials', () => {
  it('formats whole dollars, and compact amounts for charts', () => {
    expect(formatMoney(131500)).toBe('$131,500');
    expect(formatMoney(250000, { compact: true })).toBe('$250K');
    expect(formatMoney(undefined)).toBe('$0');
  });

  it('builds initials from the first two names', () => {
    expect(initials('Dana Whitfield')).toBe('DW');
    expect(initials('  priya   raman  extra ')).toBe('PR');
  });
});