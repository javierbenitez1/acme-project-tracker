import { describe, expect, it } from 'vitest';
import { IDLE_LIMIT_MS, countdown, idleState, signInNotice } from './session';

describe('idleState', () => {
  const start = 1_000_000;
  it('stays active until the last two minutes', () => {
    expect(idleState(start, start + 60_000).phase).toBe('active');
  });

  it('warns with a countdown, then expires', () => {
    expect(idleState(start, start + IDLE_LIMIT_MS - 90_000)).toEqual({ phase: 'warning', secondsLeft: 90 });
    expect(idleState(start, start + IDLE_LIMIT_MS).phase).toBe('expired');
  });
});

describe('countdown', () => {
  it('formats minutes and seconds', () => {
    expect(countdown(95)).toBe('1:35');
    expect(countdown(9)).toBe('0:09');
    expect(countdown(-3)).toBe('0:00');
  });
});

describe('signInNotice', () => {
  const previous = { created_at: '2026-10-13T21:02:00Z', device: 'Firefox on Linux' };

  it('welcomes people back with their last sign-in', () => {
    const notice = signInNotice({ previous, failed_since_previous: 0 }, 'Dana');
    expect(notice.severity).toBe('info');
    expect(notice.text).toMatch(/^Welcome back, Dana\. Your last sign-in was Oct 1[34].*Firefox on Linux\.$/);
  });

  it('warns about failed attempts', () => {
    const notice = signInNotice({ previous, failed_since_previous: 2 }, 'Dana');
    expect(notice.severity).toBe('error');
    expect(notice.text).toMatch(/2 failed sign-in attempts since your last visit/);
  });

  it('says nothing on a first ever sign-in', () => {
    expect(signInNotice({ previous: null }, 'Dana')).toBeNull();
  });
});