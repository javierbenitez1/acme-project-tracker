/** Shared helpers for anything drawn on a calendar axis (portfolio timeline, Gantt chart). */
const DAY = 86_400_000;

export function createScale(minMs, maxMs, { padRatio = 0.02, minPadDays = 2 } = {}) {
  const pad = Math.max((maxMs - minMs) * padRatio, minPadDays * DAY);
  const min = minMs - pad;
  const max = maxMs + pad;
  const percentOf = (time) => ((time - min) / (max - min)) * 100;
  return { min, max, percentOf };
}

export function monthTicks(min, max, maxTicks = 7) {
  const ticks = [];
  const cursor = new Date(min);
  cursor.setDate(1);
  cursor.setMonth(cursor.getMonth() + 1);
  while (cursor.getTime() <= max) {
    ticks.push(new Date(cursor));
    cursor.setMonth(cursor.getMonth() + 1);
  }
  const step = Math.ceil(ticks.length / maxTicks) || 1;
  return ticks.filter((_, index) => index % step === 0);
}