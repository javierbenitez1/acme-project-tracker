import StatusReportButton from '../components/StatusReport';
import { Fragment } from 'react';
import { Link as RouterLink, useParams, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  Alert, Avatar, Box, Button, Card, CardContent, Chip, Divider, List, ListItem, ListItemAvatar, ListItemText,
  Skeleton, Stack, Step, StepLabel, Stepper, Tab, Tabs, Typography,
} from '@mui/material';
import ArrowBackRounded from '@mui/icons-material/ArrowBackRounded';
import ContentCopyOutlined from '@mui/icons-material/ContentCopyOutlined';
import { useAuth } from '../auth/AuthContext';
import { api } from '../services/api';
import { useToast } from '../components/Toast';
import HealthChip, { healthText } from '../components/HealthChip';
import ScheduleTimeline, { DeliveryForecast } from '../components/ScheduleTimeline';
import RisksTab from '../components/project/RisksTab';
import ProgressCompare from '../components/ProgressCompare';
import Section from '../components/Section';
import { EmptyState, ErrorState } from '../components/PageState';
import MilestonesTab from '../components/project/MilestonesTab';
import TeamTab from '../components/project/TeamTab';
import BudgetTab from '../components/project/BudgetTab';
import { projectBriefing } from '../utils/briefing';
import { formatDate, formatMoney, initials, timeAgo } from '../utils/format';

const TABS = [
  { value: 'overview', label: 'Overview' },
  { value: 'timeline', label: 'Timeline' },
  { value: 'risks', label: 'Risks' },
  { value: 'milestones', label: 'Milestones' },
  { value: 'team', label: 'Team' },
  { value: 'budget', label: 'Budget', managersOnly: true },
  { value: 'history', label: 'History' },
];

function StatusStepper({ project }) {
  const steps = ['Planning', project.status === 'on_hold' ? 'On hold' : 'In progress', 'Completed'];
  const active = { planning: 0, active: 1, on_hold: 1, completed: 3 }[project.status] ?? 1;
  return (
    <Stepper activeStep={active} alternativeLabel aria-label="Project status">
      {steps.map((label) => (
        <Step key={label}><StepLabel error={label === 'On hold'}>{label}</StepLabel></Step>
      ))}
    </Stepper>
  );
}

function dueText(project) {
  if (project.status === 'completed') return '';
  if (project.days_remaining > 0) return ` (in ${project.days_remaining} days)`;
  if (project.days_remaining === 0) return ' (today)';
  return ` (${-project.days_remaining} days ago)`;
}

function Overview({ project, milestones, showBudget }) {
  const toast = useToast();
  const briefing = projectBriefing(project, milestones, { includeBudget: showBudget });
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(briefing);
      toast.success('Briefing copied. Paste it into an email or chat.');
    } catch {
      toast.error("Couldn't copy automatically. Select the text and copy it instead.");
    }
  };
  const facts = [
    ['Manager', project.manager_name],
    ['Department', project.department || 'Not set'],
    ['Starts', formatDate(project.start_date)],
    ['Ends', `${formatDate(project.end_date)}${dueText(project)}`],
    ['Team', `${project.member_count} ${project.member_count === 1 ? 'person' : 'people'}`],
    showBudget && ['Planned budget', formatMoney(project.budget_planned)],
  ].filter(Boolean);

  return (
    <Box sx={{ display: 'grid', gap: 3, gridTemplateColumns: { xs: '1fr', md: '3fr 2fr' }, alignItems: 'start' }}>
      <Stack spacing={3}>
        <Section title="Status briefing" subtitle="Written from the live project data. Copy it to update stakeholders."
          action={<Button size="small" startIcon={<ContentCopyOutlined />} onClick={copy}>Copy</Button>}>
          <Typography sx={{ fontSize: '1rem', lineHeight: 1.7, maxWidth: 680 }}>{briefing}</Typography>
        </Section>
        <Section title="Health" subtitle="Work done compared with time and budget used.">
          <ProgressCompare project={project} showBudget={showBudget} />
          {!project.is_archived && <DeliveryForecast projectId={project.id} />}
          {!project.is_archived && project.risk_reasons.length > 0 && (
            <Box component="ul" sx={{ mt: 2.5, mb: 0, pl: 2.5 }}>
              {project.risk_reasons.map((reason) => (
                <Typography component="li" key={reason} sx={[{ fontWeight: 500 }, ...healthText(project.health)]}>{reason}</Typography>
              ))}
            </Box>
          )}
        </Section>
      </Stack>
      <Section title="Details">
        <Box component="dl" sx={{ m: 0, display: 'grid', gridTemplateColumns: 'max-content 1fr', columnGap: 3, rowGap: 1.5 }}>
          {facts.map(([label, value]) => (
            <Fragment key={label}>
              <Typography component="dt" color="text.secondary">{label}</Typography>
              <Typography component="dd" sx={{ m: 0, fontWeight: 500 }}>{value}</Typography>
            </Fragment>
          ))}
        </Box>
        {project.description && (
          <>
            <Divider sx={{ my: 2.5 }} />
            <Typography color="text.secondary">{project.description}</Typography>
          </>
        )}
      </Section>
    </Box>
  );
}

function History({ project, milestones }) {
  const names = Object.fromEntries(milestones.map((m) => [m.id, m.name]));
  const entries = [
    ...project.date_changes.map((change) => ({
      id: `date-${change.id}`, at: change.changed_at, who: change.changed_by_name, reason: change.reason,
      title: change.entity_type === 'project' ? 'Project dates changed' : `${names[change.entity_id] || 'A milestone'} was rescheduled`,
      detail: `${formatDate(change.old_start)} to ${formatDate(change.old_end)} became ${formatDate(change.new_start)} to ${formatDate(change.new_end)}`,
    })),
    ...(project.budget_changes || []).map((change) => ({
      id: `budget-${change.id}`, at: change.changed_at, who: change.changed_by_name, reason: change.reason,
      title: 'Budget changed', detail: `${formatMoney(change.old_amount)} became ${formatMoney(change.new_amount)}`,
    })),
  ].sort((a, b) => new Date(b.at) - new Date(a.at));

  return (
    <Section title="History" subtitle="Every date and budget change, with the reason given.">
      {entries.length === 0 ? (
        <Typography color="text.secondary">No dates or budgets have changed since the project was set up.</Typography>
      ) : (
        <Box component="ol" sx={{ listStyle: 'none', m: 0, p: 0 }}>
          {entries.map((entry) => (
            <Box component="li" key={entry.id} sx={{ position: 'relative', pl: 3, pb: 2.5, borderLeft: 2, borderColor: 'divider', ml: 0.75, '&:last-child': { pb: 0 } }}>
              <Box aria-hidden="true" sx={{ position: 'absolute', left: -7, top: 4, width: 12, height: 12, borderRadius: '50%', bgcolor: 'background.paper', border: 2, borderColor: 'primary.main' }} />
              <Typography sx={{ fontWeight: 600 }}>{entry.title}</Typography>
              <Typography variant="body2">{entry.detail}</Typography>
              <Typography variant="body2" sx={{ mt: 0.5 }}>Reason: {entry.reason}</Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>{entry.who || 'Someone'}, {timeAgo(entry.at)}</Typography>
            </Box>
          ))}
        </Box>
      )}
    </Section>
  );
}

function DetailSkeleton() {
  return (
    <Stack spacing={3} aria-busy="true" aria-label="Loading the project">
      <Skeleton width={120} />
      <Skeleton variant="text" width="45%" height={48} />
      <Skeleton variant="rounded" height={80} />
      <Skeleton variant="rounded" height={360} />
    </Stack>
  );
}

export default function ProjectDetailPage() {
  const { projectId } = useParams();
  const { user } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const projectQuery = useQuery({ queryKey: ['project', projectId], queryFn: () => api.get(`projects/${projectId}`), refetchInterval: 30_000 });
  const milestonesQuery = useQuery({
    queryKey: ['milestones', { project: projectId }],
    queryFn: () => api.get(`milestones?project_id=${projectId}&include_archived=true`),
    refetchInterval: 30_000,
  });

  if (projectQuery.isPending) return <DetailSkeleton />;
  if (projectQuery.isError) {
    if (projectQuery.error.status === 404) {
      return (
        <EmptyState title="Project not found" message="It may not exist, or you may not have access to it."
          action={<Button variant="contained" component={RouterLink} to="/projects">Back to projects</Button>} />
      );
    }
    return <ErrorState error={projectQuery.error} onRetry={() => projectQuery.refetch()} />;
  }

  const project = projectQuery.data;
  const milestones = milestonesQuery.data || [];
  const showBudget = user.role !== 'employee';
  const tabs = TABS.filter((t) => showBudget || !t.managersOnly);
  const requested = searchParams.get('tab');
  const tab = tabs.some((t) => t.value === requested) ? requested : 'overview';
  const completed = project.status === 'completed';

  return (
    <Stack spacing={3}>
      <Box component="header">
        <Button component={RouterLink} to="/projects" startIcon={<ArrowBackRounded />} size="small" sx={{ mb: 1.5, color: 'text.secondary' }}>
          All projects
        </Button>
        <Box sx={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 1.5 }}>
          <Typography variant="h1">{project.name}</Typography>
          <HealthChip value={project.health} />
          {project.can_manage && <Box sx={{ ml: 'auto' }}><StatusReportButton project={project} /></Box>}
        </Box>
        <Typography color="text.secondary" sx={{ mt: 1 }}>
          Managed by {project.manager_name}{project.department ? ` in ${project.department}` : ''},
          {' '}{formatDate(project.start_date)} to {formatDate(project.end_date)}
        </Typography>
      </Box>

      {project.is_archived && (
        <Alert severity={completed ? 'success' : 'info'}>
          {completed ? 'Completed' : 'Archived'} on {formatDate(project.archived_at)}
          {project.archived_by_name ? ` by ${project.archived_by_name}` : ''}
          {project.archive_reason ? `: ${project.archive_reason.replace(/\.$/, '')}` : ''}. This project is read-only
          {completed ? '.' : '. An admin can restore it.'}
        </Alert>
      )}

      <Card><CardContent sx={{ py: 3 }}><StatusStepper project={project} /></CardContent></Card>

      <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
        <Tabs value={tab} onChange={(_, value) => setSearchParams({ tab: value }, { replace: true })}
          variant="scrollable" allowScrollButtonsMobile aria-label="Project sections">
          {tabs.map((t) => <Tab key={t.value} value={t.value} label={t.label} />)}
        </Tabs>
      </Box>

      {tab === 'overview' && <Overview project={project} milestones={milestones} showBudget={showBudget} />}
      {tab === 'timeline' && (
        <Section title="Timeline" subtitle="Bars run from each milestone's start to its due date. Arrows show which milestones wait on others. Hover a bar for details.">
          {milestonesQuery.isPending ? <Skeleton variant="rounded" height={240} />
            : milestones.length ? <ScheduleTimeline project={project} milestones={milestones} />
              : <EmptyState title="No milestones yet" message="Milestones will show up here once they're added." />}
        </Section>
      )}
      {tab === 'milestones' && <MilestonesTab project={project} milestones={milestones} loading={milestonesQuery.isPending} />}
      {tab === 'risks' && <RisksTab project={project} />}
      {tab === 'team' && <TeamTab project={project} milestones={milestones} />}
      {tab === 'budget' && <BudgetTab project={project} />}
      {tab === 'history' && <History project={project} milestones={milestones} />}
    </Stack>
  );
}