import { Fragment, useState } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import {
  Box, Card, Collapse, IconButton, Link, MenuItem, Skeleton, Stack, Table, TableBody, TableCell, TableHead, TableRow,
  TextField, Typography,
} from '@mui/material';
import ExpandMoreRounded from '@mui/icons-material/ExpandMoreRounded';
import { api } from '../services/api';
import { EmptyState, ErrorState } from '../components/PageState';
import { healthText } from '../components/HealthChip';
import { formatDate } from '../utils/format';

/** Shade a cell by how much of the 40-hour week is booked; red means over capacity. */
function cellStyle(utilization) {
  if (utilization > 100) return { bg: 'rgba(194, 65, 45, 0.75)', fg: '#FFFFFF' };
  if (utilization === 0) return { bg: 'transparent', fg: 'text.disabled' };
  const alpha = utilization >= 90 ? 0.85 : utilization >= 60 ? 0.55 : 0.28;
  return { bg: `rgba(60, 154, 153, ${alpha})`, fg: alpha > 0.5 ? '#FFFFFF' : 'text.primary' };
}

function Legend() {
  const items = [[0, 'Free'], [40, 'Under 60%'], [75, '60 to 89%'], [100, '90 to 100%'], [120, 'Over 40 hours']];
  return (
    <Box sx={{ display: 'flex', flexWrap: 'wrap', columnGap: 3, rowGap: 1, color: 'text.secondary', fontSize: '0.8125rem' }}>
      {items.map(([value, label]) => {
        const style = cellStyle(value);
        return (
          <Box key={label} sx={{ display: 'inline-flex', alignItems: 'center', gap: 1 }}>
            <Box aria-hidden="true" sx={{ width: 18, height: 14, borderRadius: '4px', bgcolor: style.bg, border: value === 0 ? 1 : 0, borderColor: 'divider' }} />
            {label}
          </Box>
        );
      })}
    </Box>
  );
}

export default function WorkloadPage() {
  const [weeks, setWeeks] = useState(6);
  const [projectId, setProjectId] = useState('');
  const [expanded, setExpanded] = useState(null);
  const projects = useQuery({ queryKey: ['projects', 'options'], queryFn: () => api.get('projects') });
  const load = useQuery({
    queryKey: ['dashboard', 'workload', weeks, projectId],
    queryFn: () => api.get(`dashboard/workload?weeks=${weeks}${projectId ? `&project_id=${projectId}` : ''}`),
    placeholderData: keepPreviousData, refetchInterval: 60_000,
  });

  const people = load.data?.people || [];
  const overBooked = people.filter((p) => p.over_allocated).length;
  const fullThisWeek = people.filter((p) => p.weeks[0]?.utilization >= 90).length;
  const available = people.filter((p) => (p.weeks[0]?.utilization ?? 0) < 50).length;

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h1">Workload</Typography>
        <Typography color="text.secondary" sx={{ mt: 1, maxWidth: 760 }}>
          Hours booked each week against a 40-hour week (8 hours a day). Select a person to see what they're booked on.
        </Typography>
      </Box>

      <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
        <TextField select size="small" fullWidth={false} label="Project" value={projectId} onChange={(event) => setProjectId(event.target.value)} sx={{ minWidth: 240 }}>
          <MenuItem value="">Everyone I can see</MenuItem>
          {(projects.data || []).map((p) => <MenuItem key={p.id} value={p.id}>{p.name}</MenuItem>)}
        </TextField>
        <TextField select size="small" fullWidth={false} label="Weeks" value={weeks} onChange={(event) => setWeeks(event.target.value)} sx={{ minWidth: 120 }}>
          {[4, 6, 8, 12].map((n) => <MenuItem key={n} value={n}>{n} weeks</MenuItem>)}
        </TextField>
      </Box>

      {load.data && (
        <Typography>
          <Box component="span" sx={overBooked ? [{ fontWeight: 600 }, ...healthText('off_track')] : { fontWeight: 600 }}>
            {overBooked ? `${overBooked} ${overBooked === 1 ? 'person is' : 'people are'} booked over 8 hours on some day.` : 'Nobody is booked over 8 hours a day.'}
          </Box>
          {' '}{fullThisWeek} fully booked this week, {available} with more than half their week free.
        </Typography>
      )}

      {load.isPending ? <Skeleton variant="rounded" height={360} />
        : load.isError ? <ErrorState error={load.error} onRetry={() => load.refetch()} />
          : people.length === 0 ? <EmptyState title="No one to show" message="People appear here once they're on a project you can see." />
            : (
              <Card sx={{ opacity: load.isPlaceholderData ? 0.6 : 1 }}>
                <Box sx={{ overflowX: 'auto' }}>
                  <Table size="small" aria-label="Hours booked per person per week">
                    <TableHead>
                      <TableRow>
                        <TableCell sx={{ minWidth: 220 }}>Person</TableCell>
                        {load.data.week_starts.map((week, index) => (
                          <TableCell key={week} align="center" sx={{ minWidth: 92, whiteSpace: 'nowrap' }}>
                            {index === 0 ? 'This week' : formatDate(week)}
                          </TableCell>
                        ))}
                        <TableCell align="right" sx={{ whiteSpace: 'nowrap' }}>Busiest day</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {people.map((person) => {
                        const open = expanded === person.user_id;
                        return (
                          <Fragment key={person.user_id}>
                            <TableRow hover sx={{ cursor: 'pointer', '& > td': { borderBottom: open ? 0 : undefined } }}
                              onClick={() => setExpanded(open ? null : person.user_id)}>
                              <TableCell>
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                  <IconButton size="small" aria-expanded={open} aria-label={`${open ? 'Hide' : 'Show'} ${person.name}'s bookings`}
                                    onClick={(event) => { event.stopPropagation(); setExpanded(open ? null : person.user_id); }}
                                    sx={{ transform: open ? 'rotate(180deg)' : 'none', transition: 'transform 150ms' }}>
                                    <ExpandMoreRounded fontSize="small" />
                                  </IconButton>
                                  <Box>
                                    <Typography sx={{ fontWeight: 600 }}>{person.name}</Typography>
                                    <Typography variant="body2" color="text.secondary">{person.job_title}</Typography>
                                  </Box>
                                </Box>
                              </TableCell>
                              {person.weeks.map((week) => {
                                const style = cellStyle(week.utilization);
                                return (
                                  <TableCell key={week.week_start} align="center" sx={{ p: 0.75 }}>
                                    <Box aria-label={`${person.name}, week of ${formatDate(week.week_start)}: ${week.hours} of 40 hours`}
                                      sx={{ borderRadius: '6px', py: 1, bgcolor: style.bg, color: style.fg, fontWeight: 600, border: week.utilization === 0 ? 1 : 0, borderColor: 'divider' }}>
                                      {week.hours ? `${week.hours}h` : '0'}
                                    </Box>
                                  </TableCell>
                                );
                              })}
                              <TableCell align="right" sx={[{ whiteSpace: 'nowrap', fontWeight: 600 }, ...(person.over_allocated ? healthText('off_track') : [])]}>
                                {person.peak_daily_hours ? `${person.peak_daily_hours}h` : 'Free'}
                                {person.peak_day && <Typography component="span" variant="body2" color="text.secondary"> on {formatDate(person.peak_day)}</Typography>}
                              </TableCell>
                            </TableRow>
                            <TableRow>
                              <TableCell colSpan={weeks + 2} sx={{ py: 0 }}>
                                <Collapse in={open} unmountOnExit>
                                  <Box sx={{ py: 2, pl: 6 }}>
                                    {person.assignments.length === 0 ? (
                                      <Typography color="text.secondary">Not booked on any open milestone during these weeks.</Typography>
                                    ) : (
                                      <Stack spacing={0.75}>
                                        {person.assignments.map((a) => (
                                          <Typography key={`${a.milestone_id}`} variant="body2">
                                            <Link component={RouterLink} to={`/projects/${a.project_id}?tab=milestones`} underline="hover">{a.milestone}</Link>
                                            {' '}in {a.project}: {Number(a.hours_per_day)}h/day, {formatDate(a.start_date)} to {formatDate(a.end_date)}
                                          </Typography>
                                        ))}
                                      </Stack>
                                    )}
                                  </Box>
                                </Collapse>
                              </TableCell>
                            </TableRow>
                          </Fragment>
                        );
                      })}
                    </TableBody>
                  </Table>
                </Box>
              </Card>
            )}
      <Legend />
    </Stack>
  );
}