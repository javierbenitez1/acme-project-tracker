import { Link as RouterLink } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  Avatar, Box, Button, Card, CardContent, Chip, List, ListItem, ListItemAvatar, ListItemButton, ListItemText, Skeleton,
  Stack, Typography,
} from '@mui/material';
import AutoModeOutlined from '@mui/icons-material/AutoModeOutlined';
import { useAuth } from '../auth/AuthContext';
import { api } from '../services/api';
import { health } from '../theme';
import HealthChip, { healthText } from '../components/HealthChip';
import PortfolioMap from '../components/PortfolioMap';
import Section from '../components/Section';
import { ErrorState } from '../components/PageState';
import { formatDue, formatMoney, initials, timeAgo } from '../utils/format';

const plural = (count, word) => `${count} ${word}${count === 1 ? '' : 's'}`;
const DELIVERABLE_STATUS = { todo: 'To do', in_progress: 'In progress', blocked: 'Blocked', done: 'Done' };

function greeting() {
  const hour = new Date().getHours();
  if (hour < 12) return 'Good morning';
  if (hour < 18) return 'Good afternoon';
  return 'Good evening';
}

/** A plain-English status line written from the live numbers. */
function briefing({ role, kpis, active, attention, myWork }) {
  if (role === 'employee') {
    if (!kpis.my_open_deliverables) return 'Nothing is assigned to you right now.';
    const overdue = myWork.filter((item) => item.is_overdue).length;
    const blocked = myWork.filter((item) => item.status === 'blocked').length;
    const extras = [overdue && `${overdue} overdue`, blocked && `${blocked} blocked`].filter(Boolean);
    return `You have ${plural(kpis.my_open_deliverables, 'open deliverable')}${extras.length ? `, ${extras.join(' and ')}` : ''}.`;
  }
  if (!active.length) return 'There are no active projects yet.';
  if (!attention.length) {
    return active.length === 1
      ? `${active[0].name} is on track, and it's the only active project.`
      : `All ${active.length} active projects are on track.`;
  }
  const worst = attention[0];
  const verb = attention.length === 1 ? 'needs' : 'need';
  const reason = worst.risk_reasons[0] ? ` ${worst.risk_reasons[0]}.` : '';
  return `${attention.length} of ${plural(active.length, 'active project')} ${verb} attention. `
    + `${worst.name} is ${health[worst.health].label.toLowerCase()}.${reason}`;
}

function StatStrip({ stats }) {
  return (
    <Card component="section" aria-label="Key numbers"
      sx={{ display: 'grid', gridTemplateColumns: { xs: 'repeat(2, 1fr)', sm: 'repeat(3, 1fr)', lg: `repeat(${stats.length}, 1fr)` } }}>
      {stats.map((stat) => (
        <Box key={stat.label} sx={{ px: 3, py: 2.25, borderRight: 1, borderBottom: 1, borderColor: 'divider', mr: '-1px', mb: '-1px' }}>
          <Typography variant="body2" color="text.secondary">{stat.label}</Typography>
          <Typography sx={[{ fontSize: '1.75rem', fontWeight: 600, lineHeight: 1.2, mt: 0.5 }, ...(stat.health && stat.value ? healthText(stat.health) : [])]}>
            {stat.value}
          </Typography>
          {stat.hint && <Typography variant="body2" color="text.secondary">{stat.hint}</Typography>}
        </Box>
      ))}
    </Card>
  );
}

function NeedsAttention({ projects }) {
  return (
    <Section title="Needs attention" subtitle="Projects that are at risk or off track, and why.">
      {projects.length === 0 ? (
        <Typography color="text.secondary">Every active project is on track.</Typography>
      ) : (
        <List disablePadding>
          {projects.map((project) => (
            <ListItemButton key={project.id} component={RouterLink} to={`/projects/${project.id}`}
              sx={{ px: 1.5, py: 1.25, borderRadius: 2, flexDirection: 'column', alignItems: 'stretch', gap: 0.75 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                <Typography sx={{ fontWeight: 600, flexGrow: 1 }}>{project.name}</Typography>
                <HealthChip value={project.health} size="small" />
              </Box>
              <Box component="ul" sx={{ m: 0, pl: 2.5, color: 'text.secondary', fontSize: '0.875rem' }}>
                {project.risk_reasons.slice(0, 3).map((reason) => <li key={reason}>{reason}</li>)}
              </Box>
              <Typography variant="body2" color="text.secondary">Managed by {project.manager_name}</Typography>
            </ListItemButton>
          ))}
        </List>
      )}
    </Section>
  );
}

function DueSoon({ items }) {
  return (
    <Section title="Milestones due soon" subtitle="Overdue, or due in the next two weeks.">
      {items.length === 0 ? (
        <Typography color="text.secondary">Nothing is due in the next two weeks.</Typography>
      ) : (
        <List disablePadding>
          {items.map((milestone) => (
            <ListItemButton key={milestone.id} component={RouterLink} to={`/projects/${milestone.project_id}`} sx={{ px: 1.5, borderRadius: 2, gap: 2 }}>
              <ListItemText primary={milestone.name} secondary={milestone.project_name} slotProps={{ primary: { sx: { fontWeight: 600 } } }} />
              <Typography variant="body2" sx={[{ fontWeight: 600, whiteSpace: 'nowrap' }, ...(milestone.is_overdue ? healthText('off_track') : [{ color: 'text.secondary' }])]}>
                {formatDue(milestone.end_date)}
              </Typography>
            </ListItemButton>
          ))}
        </List>
      )}
    </Section>
  );
}

function YourWork({ items, isEmployee }) {
  return (
    <Section title="Your work" subtitle="Open deliverables assigned to you."
      action={isEmployee ? <Button component={RouterLink} to="/my-work" size="small">Open my work</Button> : null}>
      {items.length === 0 ? (
        <Typography color="text.secondary">You're all caught up. Nothing is assigned to you right now.</Typography>
      ) : (
        <List disablePadding>
          {items.map((item) => (
            <ListItemButton key={item.id} component={RouterLink} to={isEmployee ? '/my-work' : `/projects/${item.project_id}`} sx={{ px: 1.5, borderRadius: 2, gap: 2 }}>
              <ListItemText primary={item.title} secondary={`${item.milestone_name}, ${item.project_name}`} slotProps={{ primary: { sx: { fontWeight: 600 } } }} />
              <Box sx={{ textAlign: 'right', flexShrink: 0 }}>
                <Chip size="small" variant="outlined" label={DELIVERABLE_STATUS[item.status]}
                  color={item.status === 'blocked' ? 'error' : item.status === 'in_progress' ? 'warning' : 'default'} />
                {item.due_date && (
                  <Typography variant="body2" sx={[{ mt: 0.5 }, ...(item.is_overdue ? healthText('off_track') : [{ color: 'text.secondary' }])]}>
                    {formatDue(item.due_date)}
                  </Typography>
                )}
              </Box>
            </ListItemButton>
          ))}
        </List>
      )}
    </Section>
  );
}

function RecentActivity({ items }) {
  return (
    <Section title="Recent activity" subtitle="Updates across your projects, newest first.">
      {items.length === 0 ? (
        <Typography color="text.secondary">No activity yet.</Typography>
      ) : (
        <List disablePadding sx={{ columns: { lg: 2 }, columnGap: 4 }}>
          {items.map((entry) => (
            <ListItem key={entry.id} disableGutters sx={{ breakInside: 'avoid', alignItems: 'flex-start', py: 1 }}>
              <ListItemAvatar sx={{ minWidth: 48 }}>
                <Avatar
                  aria-label={entry.actor_name || 'Automatic update'}
                  sx={{
                    width: 32, height: 32, fontSize: '0.8rem', fontWeight: 700,
                    bgcolor: entry.actor_name ? 'primary.main' : 'action.selected',
                    color: entry.actor_name ? 'primary.contrastText' : 'text.secondary',
                  }}
                >
                  {entry.actor_name ? initials(entry.actor_name) : <AutoModeOutlined fontSize="small" />}
                </Avatar>
              </ListItemAvatar>
              <ListItemText primary={entry.summary} secondary={timeAgo(entry.created_at)} slotProps={{ primary: { sx: { fontSize: '0.9rem' } } }} />
            </ListItem>
          ))}
        </List>
      )}
    </Section>
  );
}

function DashboardSkeleton() {
  return (
    <Stack spacing={3} aria-busy="true" aria-label="Loading the dashboard">
      <Box>
        <Skeleton variant="text" width={320} height={48} />
        <Skeleton variant="text" width="55%" />
      </Box>
      <Skeleton variant="rounded" height={96} />
      <Skeleton variant="rounded" height={280} />
      <Box sx={{ display: 'grid', gap: 3, gridTemplateColumns: { xs: '1fr', md: '7fr 5fr' } }}>
        <Skeleton variant="rounded" height={240} />
        <Skeleton variant="rounded" height={240} />
      </Box>
    </Stack>
  );
}

export default function DashboardPage() {
  const { user } = useAuth();
  const dashboard = useQuery({ queryKey: ['dashboard'], queryFn: () => api.get('dashboard'), refetchInterval: 30_000 });
  const milestones = useQuery({ queryKey: ['milestones', 'active'], queryFn: () => api.get('milestones'), refetchInterval: 60_000 });
  const actionSummary = useQuery({ queryKey: ['actions', 'summary'], queryFn: () => api.get('actions/summary'), refetchInterval: 30_000 });

  if (dashboard.isPending) return <DashboardSkeleton />;
  if (dashboard.isError) return <ErrorState error={dashboard.error} onRetry={() => dashboard.refetch()} />;

  const { kpis, projects, upcoming_milestones: dueSoon, my_work: myWork, recent_activity: activity } = dashboard.data;
  const isEmployee = user.role === 'employee';
  const active = projects.filter((p) => p.health !== 'completed');
  const attention = active.filter((p) => p.health === 'at_risk' || p.health === 'off_track');
  const budgetPct = kpis.budget_planned > 0 ? Math.round((100 * kpis.budget_spent) / kpis.budget_planned) : 0;

  const stats = [
    { label: 'Active projects', value: kpis.active_projects },
    { label: 'At risk', value: kpis.at_risk, health: 'at_risk' },
    { label: 'Off track', value: kpis.off_track, health: 'off_track' },
    { label: 'Overdue milestones', value: kpis.overdue_milestones, health: 'off_track' },
    !isEmployee && {
      label: 'Budget used', value: `${budgetPct}%`,
      hint: `${formatMoney(kpis.budget_spent, { compact: true })} of ${formatMoney(kpis.budget_planned, { compact: true })}`,
    },
    isEmployee
      ? { label: 'Your open deliverables', value: kpis.my_open_deliverables }
      : { label: 'Open action items', value: actionSummary.data?.open_total ?? kpis.my_open_actions },
  ].filter(Boolean);

  return (
    <Stack spacing={3}>
      <Box component="header">
        <Typography variant="h1">{greeting()}, {user.name.split(' ')[0]}</Typography>
        <Typography color="text.secondary" sx={{ mt: 1, maxWidth: 760, fontSize: '1.0625rem' }}>
          {briefing({ role: user.role, kpis, active, attention, myWork })}
        </Typography>
      </Box>

      <StatStrip stats={stats} />

      <Section
        title="Portfolio timeline"
        subtitle="Each line is a project and each station is a milestone on its due date. Select a project to open it."
        action={<Button component={RouterLink} to="/projects" size="small">All projects</Button>}
      >
        {milestones.isPending
          ? <Skeleton variant="rounded" height={180} />
          : <PortfolioMap projects={active} milestones={milestones.data || []} />}
      </Section>

      <Box sx={{ display: 'grid', gap: 3, gridTemplateColumns: { xs: '1fr', md: '7fr 5fr' } }}>
        {isEmployee ? <YourWork items={myWork} isEmployee /> : <NeedsAttention projects={attention} />}
        <DueSoon items={dueSoon} />
      </Box>

      {!isEmployee && myWork.length > 0 && <YourWork items={myWork} isEmployee={false} />}

      <RecentActivity items={activity} />
    </Stack>
  );
}