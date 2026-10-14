import { Box, Tooltip, Typography } from '@mui/material';
import useElementWidth from '../hooks/useElementWidth';
import { formatDate, parseDate, today as startOfToday } from '../utils/format';
import { createScale, monthTicks } from '../utils/timeline';

/**
 * Milestone timeline (Gantt). Bars run from each milestone's start to its due date and fill with its
 * progress. Arrows run from each prerequisite to the milestones that wait on it.
 */
const ROW = 52;
const BAR = 20;
const LABEL = 260;
const DAY = 86_400_000;
const AMBER = '#C98A12';
const RED = '#C2412D';
const STATUS_TEXT = { done: 'Done', in_progress: 'In progress', blocked: 'Blocked', not_started: 'Not started' };

const ms = (value) => parseDate(value).getTime();
const stateOf = (m) => (m.is_overdue ? 'Overdue' : STATUS_TEXT[m.status]);
const fillColor = (m) => (m.is_overdue || m.status === 'blocked' ? RED : AMBER);

function barSx(m) {
  if (m.status === 'done') return { bgcolor: 'primary.main' };
  if (m.is_overdue || m.status === 'blocked') return { bgcolor: `${RED}2E`, border: `2px solid ${RED}` };
  if (m.status === 'in_progress') return { bgcolor: `${AMBER}2E`, border: `2px solid ${AMBER}` };
  return { bgcolor: 'action.hover', border: '2px dashed', borderColor: 'text.disabled' };
}

/** Elbow connector from the end of one bar to the start of another, detouring when they touch. */
function edgePath(x1, y1, x2, y2) {
  if (x2 - x1 >= 16) return `M${x1},${y1} H${x1 + 8} V${y2} H${x2 - 1}`;
  const above = y2 - BAR / 2 - 7;
  return `M${x1},${y1} h8 V${above} H${x2 - 10} V${y2} H${x2 - 1}`;
}

function BarDetails({ milestone }) {
  return (
    <Box sx={{ p: 0.5 }}>
      <Typography sx={{ fontWeight: 700, fontSize: '0.85rem' }}>{milestone.name}</Typography>
      <Typography sx={{ fontSize: '0.8rem' }}>
        {formatDate(milestone.start_date)} to {formatDate(milestone.end_date)}, {stateOf(milestone).toLowerCase()}
      </Typography>
      <Typography sx={{ fontSize: '0.8rem' }}>
        {milestone.deliverables_done} of {milestone.deliverables_total} deliverables done ({milestone.progress}%)
      </Typography>
      {milestone.assignees.length > 0 && (
        <Typography sx={{ fontSize: '0.8rem' }}>
          Team: {milestone.assignees.map((a) => `${a.name} (${Number(a.hours_per_day)}h/day)`).join(', ')}
        </Typography>
      )}
      {milestone.dependencies.length > 0 && (
        <Typography sx={{ fontSize: '0.8rem' }}>Waits for: {milestone.dependencies.map((d) => d.name).join(', ')}</Typography>
      )}
    </Box>
  );
}

function Legend() {
  const swatch = (sx) => <Box component="span" aria-hidden="true" sx={{ width: 22, height: 12, borderRadius: '4px', boxSizing: 'border-box', display: 'inline-block', ...sx }} />;
  const items = [
    ['Done', swatch({ bgcolor: 'primary.main' })],
    ['In progress', swatch({ bgcolor: `${AMBER}2E`, border: `2px solid ${AMBER}` })],
    ['Not started', swatch({ bgcolor: 'action.hover', border: '2px dashed', borderColor: 'text.disabled' })],
    ['Overdue or blocked', swatch({ bgcolor: `${RED}2E`, border: `2px solid ${RED}` })],
    ['Waits for', <Box key="arrow" component="span" aria-hidden="true" sx={{ width: 22, borderTop: '2px dashed', borderColor: 'text.secondary', display: 'inline-block' }} />],
    ['Today', <Box key="today" component="span" aria-hidden="true" sx={{ width: 2, height: 14, bgcolor: AMBER, display: 'inline-block' }} />],
  ];
  return (
    <Box sx={{ display: 'flex', flexWrap: 'wrap', columnGap: 3, rowGap: 1, mt: 2.5, color: 'text.secondary', fontSize: '0.8125rem' }}>
      {items.map(([label, mark]) => <Box key={label} sx={{ display: 'inline-flex', alignItems: 'center', gap: 1 }}>{mark}{label}</Box>)}
    </Box>
  );
}

export default function GanttChart({ project, milestones }) {
  const [trackRef, width] = useElementWidth();
  const rows = [...milestones].sort((a, b) => ms(a.start_date) - ms(b.start_date) || a.id - b.id);
  const index = Object.fromEntries(rows.map((m, i) => [m.id, i]));
  const todayMs = startOfToday().getTime();
  const scale = createScale(
    Math.min(ms(project.start_date), todayMs, ...rows.map((m) => ms(m.start_date))),
    Math.max(ms(project.end_date) + DAY, todayMs + DAY, ...rows.map((m) => ms(m.end_date) + DAY)),
  );
  const x = (time) => (scale.percentOf(time) / 100) * width;
  const left = (m) => x(ms(m.start_date));
  const right = (m) => x(ms(m.end_date) + DAY);
  const centerY = (i) => i * ROW + ROW / 2;
  const height = rows.length * ROW;
  const edges = rows.flatMap((m) => m.depends_on.filter((id) => id in index).map((id) => ({ from: rows[index[id]], to: m })));

  return (
    <Box>
      <Box sx={{ overflowX: 'auto' }}>
        <Box sx={{ minWidth: 760, display: 'grid', gridTemplateColumns: `${LABEL}px 1fr` }}>
          <Box />
          <Box aria-hidden="true" sx={{ position: 'relative', height: 28 }}>
            {width > 0 && monthTicks(scale.min, scale.max, 8).map((tick, i) => (
              <Typography key={tick.getTime()} component="span"
                sx={{ position: 'absolute', top: 4, left: x(tick.getTime()), transform: 'translateX(-50%)', fontSize: '0.75rem', color: 'text.secondary', whiteSpace: 'nowrap' }}>
                {tick.toLocaleDateString('en-US', i === 0 || tick.getMonth() === 0 ? { month: 'short', year: 'numeric' } : { month: 'short' })}
              </Typography>
            ))}
            {width > 0 && (
              <Typography component="span"
                sx={{ position: 'absolute', top: 0, left: x(todayMs), transform: 'translateX(-50%)', px: 0.75, fontSize: '0.75rem', fontWeight: 700, color: AMBER, bgcolor: 'background.paper', zIndex: 1 }}>
                Today
              </Typography>
            )}
          </Box>

          <Box component="ol" aria-label="Milestones in start order" sx={{ listStyle: 'none', m: 0, p: 0 }}>
            {rows.map((m) => (
              <Box component="li" key={m.id}
                sx={{ height: ROW, display: 'flex', flexDirection: 'column', justifyContent: 'center', pr: 2, borderBottom: 1, borderColor: 'divider' }}>
                <Typography noWrap sx={{ fontWeight: 600, fontSize: '0.9rem' }}>{m.name}</Typography>
                <Typography noWrap variant="body2" color="text.secondary" sx={{ fontSize: '0.8rem' }}>
                  {formatDate(m.start_date)} to {formatDate(m.end_date)}, {stateOf(m).toLowerCase()}
                </Typography>
              </Box>
            ))}
          </Box>

          <Box ref={trackRef} sx={{ position: 'relative', height }}>
            {rows.map((m, i) => (
              <Box key={`row-${m.id}`} sx={{ position: 'absolute', left: 0, right: 0, top: i * ROW, height: ROW, borderBottom: 1, borderColor: 'divider' }} />
            ))}
            {width > 0 && (
              <>
                <svg width={width} height={height} aria-hidden="true" style={{ position: 'absolute', inset: 0, pointerEvents: 'none', overflow: 'visible' }}>
                  <defs>
                    <marker id="gantt-arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto">
                      <path d="M0,0 L8,4 L0,8 z" fill="var(--mui-palette-text-secondary)" />
                    </marker>
                    <marker id="gantt-arrow-done" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto">
                      <path d="M0,0 L8,4 L0,8 z" fill="var(--mui-palette-primary-main)" />
                    </marker>
                  </defs>
                  {edges.map(({ from, to }) => {
                    const done = from.status === 'done';
                    return (
                      <path key={`${from.id}-${to.id}`} fill="none" strokeWidth="1.5"
                        d={edgePath(right(from), centerY(index[from.id]), left(to), centerY(index[to.id]))}
                        stroke={done ? 'var(--mui-palette-primary-main)' : 'var(--mui-palette-text-secondary)'}
                        strokeDasharray={done ? undefined : '4 3'}
                        markerEnd={`url(#${done ? 'gantt-arrow-done' : 'gantt-arrow'})`} />
                    );
                  })}
                </svg>

                {rows.map((m, i) => {
                  const barLeft = left(m);
                  return (
                    <Tooltip key={m.id} arrow title={<BarDetails milestone={m} />}>
                      <Box tabIndex={0} role="img"
                        aria-label={`${m.name}: ${stateOf(m).toLowerCase()}, ${formatDate(m.start_date)} to ${formatDate(m.end_date)}, ${m.progress}% complete`}
                        sx={{
                          position: 'absolute', left: barLeft, width: Math.max(right(m) - barLeft, 8), top: centerY(i) - BAR / 2,
                          height: BAR, borderRadius: '6px', boxSizing: 'border-box', overflow: 'hidden', zIndex: 1,
                          '&:focus-visible': { outline: '2px solid', outlineColor: 'secondary.main', outlineOffset: 2 },
                          ...barSx(m),
                        }}>
                        {m.status !== 'done' && m.progress > 0 && (
                          <Box sx={{ position: 'absolute', top: 0, bottom: 0, left: 0, width: `${m.progress}%`, bgcolor: fillColor(m), opacity: 0.85 }} />
                        )}
                      </Box>
                    </Tooltip>
                  );
                })}

                <Box aria-hidden="true" sx={{ position: 'absolute', top: 0, bottom: 0, left: x(todayMs), width: 2, ml: '-1px', bgcolor: AMBER, opacity: 0.6, zIndex: 2, pointerEvents: 'none' }} />
              </>
            )}
          </Box>
        </Box>
      </Box>
      <Legend />
    </Box>
  );
}