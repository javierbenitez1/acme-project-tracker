import { describe, expect, it } from 'vitest';
import { bufferPhrase, bufferText, forecastSummary, slackText } from './schedule';

describe('bufferText', () => {
  it('explains the buffer in days', () => {
    expect(bufferText({ buffer_days: 9 })).toMatch(/slip 9 days in total/);
    expect(bufferText({ buffer_days: 1 })).toMatch(/slip 1 day in total/);
  });

  it('warns when there is no buffer, and handles finished projects', () => {
    expect(bufferText({ buffer_days: 0 })).toMatch(/no buffer/);
    expect(bufferText({ buffer_days: null })).toMatch(/Every milestone is done/);
  });
});

describe('bufferPhrase', () => {
  it('states the buffer briefly', () => {
    expect(bufferPhrase(9)).toBe('9 days of buffer');
    expect(bufferPhrase(0)).toBe('no buffer left');
    expect(bufferPhrase(null)).toBe('');
  });
});

describe('slackText', () => {
  it('labels slack for one milestone', () => {
    expect(slackText(0)).toBe('No slack');
    expect(slackText(6)).toBe('Can slip 6 days');
    expect(slackText(undefined)).toBe('');
  });
});

describe('forecastSummary', () => {
  it('flags a late finish as a warning with the number of days', () => {
    const summary = forecastSummary({ status: 'late', projected_end: '2026-11-20', days_late: 12 });
    expect(summary.severity).toBe('warning');
    expect(summary.text).toMatch(/12 days after its end date/);
  });

  it('describes early and on-time finishes', () => {
    expect(forecastSummary({ status: 'early', projected_end: '2026-11-01', days_late: -5 }).text).toMatch(/5 days ahead/);
    expect(forecastSummary({ status: 'on_time', projected_end: '2026-11-01', days_late: 1 }).text).toMatch(/on schedule/);
  });

  it('is honest when it cannot forecast yet', () => {
    expect(forecastSummary({ status: 'not_enough_data' }).severity).toBe('info');
    expect(forecastSummary({ status: 'inactive' })).toBeNull();
    expect(forecastSummary(undefined)).toBeNull();
  });
});
