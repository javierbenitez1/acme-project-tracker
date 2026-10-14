import { useState } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  Box, Card, CardContent, LinearProgress, Link, MenuItem, Skeleton, Stack, TextField, Typography,
} from '@mui/material';
import { api } from '../services/api';
import useApiMutation from '../hooks/useApiMutation';
import Section from '../components/Section';
import { EmptyState, ErrorState } from '../components/PageState';
import { BlockedNoteDialog } from '../components/project/DeliverableDialog';
import { healthText } from '../components/HealthChip';
import { formatDate, formatDue } from '../utils/format';

const WORK_STATUS = [['todo', 'To do'], ['in_progress', 'In progress'], ['blocked', 'Blocked'], ['done', 'Done']];
const GROUPS = [
  { status: 'blocked', title: 'Blocked', empty: 'Nothing is blocked.' },
  { status: 'in_progress', title: 'In progress', empty: 'Nothing in progress yet. Pick something from To do.' },
  { status: 'todo', title: 'To do', empty: 'Nothing waiting on you.' },
  { status: 'done', title: 'Done recently', empty: 'Nothing finished yet.' },
];
const labelOf = (value) => WORK_STATUS.find(([key]) => key === value)?.[1] || value;

function WorkCard({ item, onBlock }) {
  const update = useApiMutation((status) => api.put(`deliverables/${item.id}`, { status }), {
    success: (data) => (data.milestone_ready
      ? `Done. Every deliverable in ${data.milestone_name} is finished, so your manager can close it.`
      : `${data.title} is now ${labelOf(data.status).toLowerCase()}.`),
  });
  const locked = item.milestone_status === 'done';
  const dueText = item.due_date ? (item.status === 'done' ? `Was due ${formatDate(item.due_date)}` : formatDue(item.due_date)) : 'No due date';

  return (
    <Card>
      <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
        <Typography sx={{ fontWeight: 600 }}>{item.title}</Typography>
        <Typography variant="body2" color="text.secondary">
          <Link component={RouterLink} to={`/projects/${item.project_id}?tab=milestones`} color="inherit" underline="hover">{item.project_name}</Link>
          , {item.milestone_name}
        </Typography>
        {item.status === 'blocked' && item.status_note && (
          <Typography variant="body2" sx={[{ mt: 1 }, ...healthText('off_track')]}>Blocked: {item.status_note}</Typography>
        )}
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1.5, mt: 1.5, flexWrap: 'wrap' }}>
          <Typography variant="body2" sx={item.is_overdue && item.status !== 'done' ? healthText('off_track') : { color: 'text.secondary' }}>{dueText}</Typography>
          <TextField select size="small" fullWidth={false} value={item.status} disabled={locked || update.isPending}
            onChange={(event) => (event.target.value === 'blocked' ? onBlock(item) : update.mutate(event.target.value))}
            sx={{ minWidth: 150 }} slotProps={{ select: { SelectDisplayProps: { 'aria-label': `Status of ${item.title}` } } }}>
            {WORK_STATUS.map(([key, text]) => <MenuItem key={key} value={key}>{text}</MenuItem>)}
          </TextField>
        </Box>
      </CardContent>
    </Card>
  );
}

function MyHours({ person }) {
  if (!person) return null;
  return (
    <Section title="Your bookings" subtitle="Hours booked each week across all your milestones. A full week is 40 hours.">
      <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 2.5 }}>
        {person.weeks.map((week, index) => (
          <Box key={week.week_start}>
            <Typography variant="body2" color="text.secondary">{index === 0 ? 'This week' : `Week of ${formatDate(week.week_start)}`}</Typography>
            <Typography sx={{ fontWeight: 600, fontSize: '1.25rem' }}>
              {week.hours}h <Typography component="span" variant="body2" color="text.secondary">of 40</Typography>
            </Typography>
            <LinearProgress variant="determinate" value={Math.min(week.utilization, 100)} color={week.utilization > 100 ? 'error' : 'primary'}
              sx={{ mt: 1, height: 6, borderRadius: 3 }} aria-label={`${week.hours} of 40 hours booked`} />
          </Box>
        ))}
      </Box>
      {person.assignments.length > 0 && (
        <Typography variant="body2" color="text.secondary" sx={{ mt: 2.5 }}>
          Booked on {person.assignments.map((a) => `${a.milestone} (${a.project}, ${Number(a.hours_per_day)}h/day until ${formatDate(a.end_date)})`).join('; ')}.
        </Typography>
      )}
    </Section>
  );
}

export default function MyWorkPage() {
  const [blocking, setBlocking] = useState(null);
  const work = useQuery({ queryKey: ['deliverables', 'mine'], queryFn: () => api.get('deliverables?assignee_id=me'), refetchInterval: 30_000 });
  const hours = useQuery({ queryKey: ['dashboard', 'workload', 'me'], queryFn: () => api.get('dashboard/workload?weeks=4'), refetchInterval: 60_000 });

  if (work.isPending) return <Stack spacing={3}><Skeleton width={240} height={48} /><Skeleton variant="rounded" height={420} /></Stack>;
  if (work.isError) return <ErrorState error={work.error} onRetry={() => work.refetch()} />;

  const items = work.data;
  const open = items.filter((item) => item.status !== 'done');
  const overdue = open.filter((item) => item.is_overdue).length;
  const grouped = Object.fromEntries(GROUPS.map((g) => [g.status, items.filter((item) => item.status === g.status)]));
  grouped.done = grouped.done.sort((a, b) => String(b.completed_at).localeCompare(String(a.completed_at))).slice(0, 8);

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h1">My work</Typography>
        <Typography color="text.secondary" sx={{ mt: 1 }}>
          {open.length ? `${open.length} open ${open.length === 1 ? 'deliverable' : 'deliverables'}${overdue ? `, ${overdue} overdue` : ''}. Change a status and your manager sees it right away.` : "You're all caught up."}
        </Typography>
      </Box>
      <MyHours person={hours.data?.people?.[0]} />
      {items.length === 0 ? (
        <EmptyState title="Nothing is assigned to you yet" message="When your manager assigns you a deliverable, it shows up here." />
      ) : (
        <Box sx={{ display: 'grid', gap: 2.5, gridTemplateColumns: { xs: '1fr', md: 'repeat(2, 1fr)', xl: 'repeat(4, 1fr)' }, alignItems: 'start' }}>
          {GROUPS.map((group) => (
            <Box key={group.status} component="section" aria-label={group.title}>
              <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 1, mb: 1.5 }}>
                <Typography variant="h3" component="h2">{group.title}</Typography>
                <Typography color="text.secondary">{grouped[group.status].length}</Typography>
              </Box>
              <Stack spacing={1.5}>
                {grouped[group.status].length === 0
                  ? <Typography variant="body2" color="text.secondary">{group.empty}</Typography>
                  : grouped[group.status].map((item) => <WorkCard key={item.id} item={item} onBlock={setBlocking} />)}
              </Stack>
            </Box>
          ))}
        </Box>
      )}
      {blocking && <BlockedNoteDialog item={blocking} onClose={() => setBlocking(null)} />}
    </Stack>
  );
}