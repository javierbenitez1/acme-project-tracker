/** Session safety rules shared by the idle sign-out and the sign-in notices. */
export const IDLE_LIMIT_MS = 15 * 60 * 1000;
export const WARNING_MS = 2 * 60 * 1000;
export const ACTIVITY_KEY = 'throughline:last-activity';

/** Where a session stands after a period without activity: active, warning (with seconds left) or expired. */
export function idleState(lastActivity, now, limit = IDLE_LIMIT_MS, warning = WARNING_MS) {
  const left = limit - (now - lastActivity);
  if (left <= 0) return { phase: 'expired', secondsLeft: 0 };
  if (left <= warning) return { phase: 'warning', secondsLeft: Math.ceil(left / 1000) };
  return { phase: 'active', secondsLeft: Math.ceil(left / 1000) };
}

/** 95 seconds becomes "1:35". */
export function countdown(seconds) {
  const s = Math.max(0, seconds);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}

/** "Oct 13, 9:02 PM" in the viewer's own time zone. */
export function signInTime(iso) {
  return new Date(iso).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
}

/** The notice shown once after signing in: a security warning if there were failed attempts, otherwise a welcome back. */
export function signInNotice(summary, firstName) {
  if (!summary?.previous) return null;
  const last = `${signInTime(summary.previous.created_at)}, ${summary.previous.device || 'unknown device'}`;
  const failed = summary.failed_since_previous || 0;
  if (failed > 0) {
    return {
      severity: 'error',
      text: `Security notice: ${failed} failed sign-in attempt${failed === 1 ? '' : 's'} since your last visit (${last}). If that wasn't you, change your password.`,
    };
  }
  return { severity: 'info', text: `Welcome back, ${firstName}. Your last sign-in was ${last}.` };
}