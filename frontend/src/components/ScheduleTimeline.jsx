import { Fragment, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Alert, Box, Chip, FormControlLabel, Stack, Switch, Typography } from '@mui/material';
import ArrowForwardRounded from '@mui/icons-material/ArrowForwardRounded';
import { api } from '../services/api';
import GanttChart from './GanttChart';
import { formatDate } from '../utils/format';
import { CRITICAL_COLOR as CRITICAL, bufferPhrase, bufferText, forecastSummary, slackText } from '../utils/schedule';

/** Critical path and delivery forecast for one project, shared by the Overview and Timeline tabs. */
export function useSchedule(projectId) {
  return useQuery({
    queryKey: ['schedule', String(projectId)],
    queryFn: () => api.get(`milestones/schedule?project_id=${projectId}`),
    refetchInterval: 30_000,
  });
}

/** The delivery forecast as a short alert, used on the Overview tab. */
export function DeliveryForecast({ projectId }) {
  const schedule = useSchedule(projectId);
  const summary = forecastSummary(schedule.data?.forecast);
  if (!summary) return null;
  const buffer = schedule.data.buffer_days;
  return (
    <Alert severity={summary.severity} sx={{ mt: 2.5 }}>
      {summary.text}
      {buffer !== null && buffer !== undefined && ` The critical path has ${bufferPhrase(buffer)}.`}
    </Alert>
  );
}

function CriticalChain({ milestones }) {
  return (
    <Box component="ol" aria-label="Critical path in order" sx={{ listStyle: 'none', m: 0, p: 0, display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 1 }}>
      {milestones.map((m, i) => (
        <Fragment key={m.id}>
          {i > 0 && <ArrowForwardRounded aria-hidden="true" fontSize="small" sx={{ color: CRITICAL }} />}
          <Box component="li">
            <Chip variant="outlined" label={`${m.name}, due ${formatDate(m.end_date)}`}
              sx={{ borderColor: CRITICAL, borderWidth: 2, fontWeight: 600 }} />
          </Box>
        </Fragment>
      ))}
    </Box>
  );
}

function SlackList({ milestones, slack, critical }) {
  const rows = milestones
    .filter((m) => slack[m.id] !== undefined)
    .sort((a, b) => slack[a.id] - slack[b.id] || a.start_date.localeCompare(b.start_date));
  if (!rows.length) return null;
  return (
    <Box>
      <Typography sx={{ fontWeight: 600, mb: 1 }}>How far each open milestone can slip</Typography>
      <Box component="dl" sx={{ m: 0, display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) max-content', columnGap: 3, rowGap: 1 }}>
        {rows.map((m) => (
          <Fragment key={m.id}>
            <Typography component="dt" noWrap title={m.name}>{m.name}</Typography>
            <Typography component="dd" sx={{ m: 0, fontWeight: 600 }}>
              {slackText(slack[m.id])}{critical.has(m.id) ? ', critical path' : ''}
            </Typography>
          </Fragment>
        ))}
      </Box>
    </Box>
  );
}

/** The Gantt chart plus critical path analysis: which milestones drive the end date, and how much each can slip. */
export default function ScheduleTimeline({ project, milestones }) {
  const [highlight, setHighlight] = useState(true);
  const schedule = useSchedule(project.id);
  const data = schedule.data;
  const chain = data?.critical_path || [];
  const criticalIds = new Set(chain.map((m) => m.id));
  const forecast = forecastSummary(data?.forecast);

  return (
    <Stack spacing={3}>
      {schedule.isError && (
        <Alert severity="warning">The critical path couldn't be loaded right now. The timeline below is still current.</Alert>
      )}
      {chain.length > 0 && (
        <Box>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 1, mb: 0.5 }}>
            <Typography sx={{ fontWeight: 600 }}>Critical path</Typography>
            <FormControlLabel control={<Switch checked={highlight} onChange={(event) => setHighlight(event.target.checked)} />}
              label="Highlight on the chart" />
          </Box>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
            {bufferText(data)} A delay anywhere on this chain delays the whole project.
          </Typography>
          <CriticalChain milestones={chain} />
        </Box>
      )}
      {forecast && <Alert severity={forecast.severity}>{forecast.text}</Alert>}
      <GanttChart project={project} milestones={milestones} critical={highlight && criticalIds.size ? criticalIds : null} />
      {data && <SlackList milestones={milestones} slack={data.slack} critical={criticalIds} />}
    </Stack>
  );
}
