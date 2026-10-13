import { Link as RouterLink } from 'react-router-dom';
import { useMediaQuery } from 'react-responsive';
import { Box, ButtonBase, Tooltip, Typography } from '@mui/material';
import HealthChip from './HealthChip';
import { health } from '../theme';
import { formatDate, parseDate, today as startOfToday } from '../utils/format';

/**
 * The portfolio timeline: every project is a line on one shared calendar, and its milestones are
 * stations placed on their due dates. The line is solid up to today and dotted after it.
 */
const LABEL_WIDTH = 248;
const GAP = 24;
const AMBER = '#C98A12';
const RED = '#C2412D';
const DAY = 86_400_000;
const STATUS_LABEL = { done: 'done', in_progress: 'in progress', blocked: 'blocked', not_started: 'not started' };

function stationStyle(milestone, todayMs) {
  const overdue = milestone.status !== 'done' && parseDate(milestone.end_date).getTime() < todayMs;
  if (milestone.status === 'done') return { size: 12, sx: { bgcolor: 'primary.main', border: '2px solid', borderColor: 'primary.main' } };
  if (overdue || milestone.status === 'blocked') return { size: 14, sx: { bgcolor: RED, border: `2px solid ${RED}` }, overdue };
  if (milestone.status === 'in_progress') return { size: 15, sx: { bgcolor: 'background.paper', border: `3px solid ${AMBER}` } };
  return { size: 12, sx: { bgcolor: 'background.paper', border: '2px solid', borderColor: 'text.disabled' } };
}

function monthTicks(min, max) {
  const ticks = [];
  const cursor = new Date(min);
  cursor.setDate(1);
  cursor.setMonth(cursor.getMonth() + 1);
  while (cursor.getTime() <= max) {
    ticks.push(new Date(cursor));
    cursor.setMonth(cursor.getMonth() + 1);
  }
  const step = Math.ceil(ticks.length / 7) || 1;
  return ticks.filter((_, index) => index % step === 0);
}

function Legend() {
  const swatch = (sx, size = 12) => (
    <Box component="span" aria-hidden="true" sx={{ width: size, height: size, borderRadius: '50%', boxSizing: 'border-box', display: 'inline-block', ...sx }} />
  );
  const items = [
    ['Done', swatch({ bgcolor: 'primary.main' })],
    ['In progress', swatch({ bgcolor: 'background.paper', border: `3px solid ${AMBER}` }, 14)],
    ['Not started', swatch({ bgcolor: 'background.paper', border: '2px solid', borderColor: 'text.disabled' })],
    ['Overdue or blocked', swatch({ bgcolor: RED })],
    ['Today', <Box key="t" component="span" aria-hidden="true" sx={{ width: 2, height: 14, bgcolor: AMBER, display: 'inline-block' }} />],
  ];
  return (
    <Box sx={{ display: 'flex', flexWrap: 'wrap', columnGap: 3, rowGap: 1, mt: 2.5, color: 'text.secondary', fontSize: '0.8125rem' }}>
      {items.map(([label, mark]) => (
        <Box key={label} sx={{ display: 'inline-flex', alignItems: 'center', gap: 1 }}>{mark}{label}</Box>
      ))}
    </Box>
  );
}

export default function PortfolioMap({ projects, milestones = [] }) {
  const narrow = useMediaQuery({ maxWidth: 699 });
  if (!projects.length) {
    return <Typography color="text.secondary">No active projects to show yet.</Typography>;
  }

  const todayMs = startOfToday().getTime();
  let min = Math.min(...projects.map((p) => parseDate(p.start_date).getTime()), todayMs);
  let max = Math.max(...projects.map((p) => parseDate(p.end_date).getTime()), todayMs);
  const pad = Math.max((max - min) * 0.03, 3 * DAY);
  min -= pad;
  max += pad;
  const pct = (ms) => ((ms - min) / (max - min)) * 100;
  const pos = (value) => pct(parseDate(value).getTime());
  const todayPct = pct(todayMs);

  const offset = narrow ? 0 : LABEL_WIDTH + GAP;
  const acrossTrack = (percent) => `calc(${offset}px + (100% - ${offset}px) * ${percent / 100})`;

  const byProject = {};
  milestones.forEach((m) => { (byProject[m.project_id] ||= []).push(m); });

  return (
    <Box>
      <Box sx={{ position: 'relative' }}>
        <Box aria-hidden="true" sx={{ position: 'relative', height: 26 }}>
          {monthTicks(min, max).map((tick) => (
            <Typography key={tick.getTime()} component="span" color="text.secondary"
              sx={{ position: 'absolute', top: 4, left: acrossTrack(pct(tick.getTime())), transform: 'translateX(-50%)', fontSize: '0.75rem', whiteSpace: 'nowrap' }}>
              {tick.toLocaleDateString('en-US', tick.getMonth() === 0 ? { month: 'short', year: 'numeric' } : { month: 'short' })}
            </Typography>
          ))}
        </Box>

        <Box aria-hidden="true" sx={{ position: 'absolute', top: 26, bottom: 0, left: acrossTrack(todayPct), width: 2, ml: '-1px', bgcolor: AMBER, opacity: 0.6, borderRadius: 1, pointerEvents: 'none' }} />
        <Typography aria-hidden="true" component="span"
          sx={{ position: 'absolute', top: 0, left: acrossTrack(todayPct), transform: 'translateX(-50%)', px: 0.75, fontSize: '0.75rem', fontWeight: 700, color: AMBER, bgcolor: 'background.paper', zIndex: 1 }}>
          Today
        </Typography>

        <Box component="ul" aria-label="Projects on the timeline" sx={{ listStyle: 'none', m: 0, p: 0 }}>
          {projects.map((project) => {
            const info = health[project.health] || health.on_track;
            const items = (byProject[project.id] || []).slice().sort((a, b) => parseDate(a.end_date) - parseDate(b.end_date));
            const startPct = pos(project.start_date);
            const endPct = pos(project.end_date);
            const nowPct = Math.min(Math.max(todayPct, startPct), endPct);
            const summary = `${project.name}, ${info.label.toLowerCase()}, ${project.progress}% complete, `
              + `${project.milestones_done} of ${project.milestone_count} milestones done`;
            return (
              <Box component="li" key={project.id}>
                <ButtonBase
                  component={RouterLink}
                  to={`/projects/${project.id}`}
                  aria-label={`${summary}. Open project.`}
                  sx={{
                    width: '100%', display: 'grid', gridTemplateColumns: narrow ? '1fr' : `${LABEL_WIDTH}px 1fr`,
                    columnGap: `${GAP}px`, rowGap: 0.5, alignItems: 'center', textAlign: 'left', py: 1.5, borderRadius: 2,
                    '&:hover': { bgcolor: 'action.hover' },
                    '&.Mui-focusVisible': { outline: '2px solid', outlineColor: 'secondary.main' },
                  }}
                >
                  <Box sx={{ minWidth: 0, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1, pl: 1 }}>
                    <Typography noWrap sx={{ fontWeight: 600 }}>{project.name}</Typography>
                    <HealthChip value={project.health} size="small" />
                  </Box>
                  <Box sx={{ position: 'relative', height: 30 }}>
                    <Box sx={{ position: 'absolute', top: '50%', mt: '-2px', height: 4, borderRadius: 2, bgcolor: info.color, left: `${startPct}%`, width: `${Math.max(nowPct - startPct, 0)}%` }} />
                    <Box sx={{ position: 'absolute', top: '50%', mt: '-1.5px', borderTop: `3px dotted ${info.color}`, opacity: 0.5, left: `${nowPct}%`, width: `${Math.max(endPct - nowPct, 0)}%` }} />
                    {items.map((milestone) => {
                      const style = stationStyle(milestone, todayMs);
                      const state = style.overdue ? 'overdue' : STATUS_LABEL[milestone.status];
                      return (
                        <Tooltip key={milestone.id} arrow title={`${milestone.name}: ${state}, due ${formatDate(milestone.end_date)}`}>
                          <Box component="span"
                            sx={{ position: 'absolute', top: '50%', left: `${pos(milestone.end_date)}%`, width: style.size, height: style.size, transform: 'translate(-50%, -50%)', borderRadius: '50%', boxSizing: 'border-box', zIndex: 1, ...style.sx }} />
                        </Tooltip>
                      );
                    })}
                  </Box>
                </ButtonBase>
              </Box>
            );
          })}
        </Box>
      </Box>
      <Legend />
    </Box>
  );
}