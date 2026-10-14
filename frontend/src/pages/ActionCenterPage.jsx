import { useState } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import {
  Box, Button, Card, Chip, Link, MenuItem, Skeleton, Stack, TextField, ToggleButton, ToggleButtonGroup, Typography,
} from '@mui/material';
import AddRounded from '@mui/icons-material/AddRounded';
import { useAuth } from '../auth/AuthContext';
import { api } from '../services/api';
import useApiMutation from '../hooks/useApiMutation';
import useFormState from '../hooks/useFormState';
import FormDialog from '../components/FormDialog';
import { EmptyState, ErrorState } from '../components/PageState';
import { healthText } from '../components/HealthChip';
import { formatDate, formatDue, timeAgo, toIsoDate } from '../utils/format';

const PRIORITIES = [
  { value: 'critical', label: 'Critical', color: '#C2412D' },
  { value: 'high', label: 'High', color: '#C98A12' },
  { value: 'medium', label: 'Medium', color: '#2445C8' },
  { value: 'low', label: 'Low', color: '#5A6B85' },
];
const VIEWS = [['active', 'Open'], ['done', 'Resolved'], ['dismissed', 'Dismissed'], ['all', 'All']];
const isOpen = (item) => item.status === 'open' || item.status === 'in_progress';

function targetOf(item) {
  if (item.entity_type === 'user') return '/workload';
  if (!item.project_id) return null;
  if (item.entity_type === 'milestone' || item.entity_type === 'deliverable') return `/projects/${item.project_id}?tab=milestones`;
  if (item.rule_key?.startsWith('project_over_budget')) return `/projects/${item.project_id}?tab=budget`;
  return `/projects/${item.project_id}`;
}

function CloseDialog({ item, status, onClose }) {
  const form = useFormState({ resolution_note: '' });
  const save = useApiMutation((body) => api.put(`actions/${item.id}`, body), {
    success: status === 'done' ? 'Marked done. Your note is saved to the audit log.' : 'Dismissed. Your reason is saved to the audit log.',
    onSuccess: onClose,
    onError: form.fail,
  });
  function submit() {
    const note = form.values.resolution_note.trim();
    if (!form.check({ resolution_note: !note && 'Add a short note so others know what happened.' })) return;
    save.mutate({ status, resolution_note: note });
  }
  return (
    <FormDialog title={status === 'done' ? `Mark "${item.title}" done` : `Dismiss "${item.title}"`}
      submitLabel={status === 'done' ? 'Mark done' : 'Dismiss'} busy={save.isPending} error={form.formError} onSubmit={submit} onClose={onClose}>
      <TextField label={status === 'done' ? 'What was done?' : "Why doesn't it need action?"} required multiline minRows={3} autoFocus
        {...form.field('resolution_note', 'Admins can see this note in the audit log.')} />
    </FormDialog>
  );
}

function NewActionDialog({ me, onClose }) {
  const form = useFormState({ title: '', description: '', priority: 'medium', project_id: '', assignee_id: '', due_date: '' });
  const values = form.values;
  const projects = useQuery({ queryKey: ['projects', 'options'], queryFn: () => api.get('projects') });
  const members = useQuery({
    queryKey: ['project', values.project_id, 'members'],
    queryFn: () => api.get(`projects/${values.project_id}/members`),
    enabled: Boolean(values.project_id),
  });
  const people = useQuery({
    queryKey: ['users', 'assignable', me.role],
    queryFn: () => api.get(me.role === 'admin' ? 'users' : `users?manager_id=${me.id}`),
    enabled: !values.project_id,
  });
  const options = values.project_id ? (members.data || []) : [me, ...(people.data || []).filter((u) => u.id !== me.id)];
  const save = useApiMutation((body) => api.post('actions', body), { success: (data) => `Added "${data.title}".`, onSuccess: onClose, onError: form.fail });

  function submit() {
    const today = toIsoDate(new Date());
    const ok = form.check({
      title: !values.title.trim() && 'Say what needs to be done.',
      assignee_id: values.project_id && !values.assignee_id && 'Choose someone on the project team.',
      due_date: values.due_date && values.due_date < today && "Can't be in the past.",
    });
    if (!ok) return;
    save.mutate({
      title: values.title.trim(), description: values.description.trim() || null, priority: values.priority,
      due_date: values.due_date || null,
      ...(values.project_id ? { project_id: Number(values.project_id) } : {}),
      ...(values.assignee_id ? { assignee_id: Number(values.assignee_id) } : {}),
    });
  }

  return (
    <FormDialog title="New action item" submitLabel="Add item" busy={save.isPending} error={form.formError} onSubmit={submit} onClose={onClose}>
      <TextField label="What needs to be done" required autoFocus {...form.field('title')} />
      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
        <TextField select label="Priority" {...form.field('priority')}>
          {PRIORITIES.map((p) => <MenuItem key={p.value} value={p.value}>{p.label}</MenuItem>)}
        </TextField>
        <TextField label="Due date" type="date" {...form.field('due_date')}
          slotProps={{ inputLabel: { shrink: true }, htmlInput: { min: toIsoDate(new Date()) } }} />
      </Stack>
      <TextField select label="Project" value={values.project_id}
        onChange={(event) => { form.set('project_id', event.target.value); form.set('assignee_id', ''); }}
        helperText="Optional. Linking a project lets you assign anyone on its team.">
        <MenuItem value="">No project</MenuItem>
        {(projects.data || []).map((p) => <MenuItem key={p.id} value={p.id}>{p.name}</MenuItem>)}
      </TextField>
      <TextField select label="Assign to" {...form.field('assignee_id', values.project_id ? undefined : 'Leave empty to assign it to yourself.')}>
        {!values.project_id && <MenuItem value="">Me</MenuItem>}
        {options.map((person) => <MenuItem key={person.id} value={person.id}>{person.name}{person.id === me.id ? ' (you)' : ''}</MenuItem>)}
      </TextField>
      <TextField label="Details" multiline minRows={2} {...form.field('description')} />
    </FormDialog>
  );
}

function ActionItem({ item, me, onClose }) {
  const start = useApiMutation(() => api.put(`actions/${item.id}`, { status: 'in_progress' }), { success: `Started "${item.title}".` });
  const reopen = useApiMutation(() => api.put(`actions/${item.id}`, { status: 'open' }), { success: `Reopened "${item.title}".` });
  const priority = PRIORITIES.find((p) => p.value === item.priority);
  const target = targetOf(item);
  const meta = [
    item.source === 'system' ? 'Raised automatically' : `Added by ${item.created_by_name}`,
    item.assignee_id !== me.id && item.assignee_name ? `for ${item.assignee_name}` : null,
  ].filter(Boolean).join(' ');

  return (
    <Card component="article" aria-label={item.title} sx={{ display: 'flex' }}>
      <Box aria-hidden="true" sx={{ width: 5, flexShrink: 0, bgcolor: priority.color }} />
      <Box sx={{ p: 2.25, flexGrow: 1, minWidth: 0 }}>
        <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1.5, flexWrap: 'wrap' }}>
          <Box sx={{ flexGrow: 1, minWidth: 220 }}>
            <Typography sx={{ fontWeight: 600 }}>{item.title}</Typography>
            {item.description && <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, maxWidth: 760 }}>{item.description}</Typography>}
          </Box>
          <Stack direction="row" spacing={1}>
            <Chip size="small" label={priority.label} sx={{ color: priority.color, bgcolor: `${priority.color}1F` }} />
            {item.status === 'in_progress' && <Chip size="small" label="In progress" variant="outlined" />}
          </Stack>
        </Box>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
          {meta}
          {item.project_name && <>, {target ? <Link component={RouterLink} to={target} underline="hover">{item.project_name}</Link> : item.project_name}</>}
          {item.due_date && isOpen(item) && <Box component="span" sx={item.due_date < toIsoDate(new Date()) ? healthText('off_track') : undefined}>, {formatDue(item.due_date).toLowerCase()}</Box>}
        </Typography>
        {!isOpen(item) && (
          <Typography variant="body2" sx={{ mt: 1 }}>
            {item.status === 'done' ? 'Resolved' : 'Dismissed'} by {item.resolved_by_name || 'Throughline'} {timeAgo(item.resolved_at)}
            {item.resolution_note ? `: ${item.resolution_note}` : ''}
          </Typography>
        )}
        <Box sx={{ display: 'flex', gap: 1, mt: 1.5, flexWrap: 'wrap', alignItems: 'center' }}>
          {isOpen(item) && item.source === 'manual' && item.status === 'open' && (
            <Button size="small" variant="outlined" onClick={() => start.mutate()} disabled={start.isPending}>Start</Button>
          )}
          {isOpen(item) && item.source === 'manual' && (
            <Button size="small" variant="contained" onClick={() => onClose(item, 'done')}>Mark done</Button>
          )}
          {isOpen(item) && <Button size="small" color="inherit" onClick={() => onClose(item, 'dismissed')}>Dismiss</Button>}
          {isOpen(item) && item.source === 'system' && (
            <Typography variant="body2" color="text.secondary">This closes on its own once the problem is fixed.</Typography>
          )}
          {item.status === 'dismissed' && (
            <Button size="small" color="inherit" onClick={() => reopen.mutate()} disabled={reopen.isPending}>Reopen</Button>
          )}
          {target && isOpen(item) && <Button size="small" component={RouterLink} to={target}>Go to it</Button>}
        </Box>
      </Box>
    </Card>
  );
}

export default function ActionCenterPage() {
  const { user } = useAuth();
  const [view, setView] = useState('active');
  const [closing, setClosing] = useState(null);
  const [creating, setCreating] = useState(false);
  const items = useQuery({
    queryKey: ['actions', 'list', view], queryFn: () => api.get(`actions?status=${view}`),
    placeholderData: keepPreviousData, refetchInterval: 30_000,
  });
  const summary = useQuery({ queryKey: ['actions', 'summary'], queryFn: () => api.get('actions/summary'), refetchInterval: 30_000 });
  const canCreate = user.role !== 'employee';

  let content;
  if (items.isPending) content = <Stack spacing={1.5}>{[0, 1, 2].map((i) => <Skeleton key={i} variant="rounded" height={120} />)}</Stack>;
  else if (items.isError) content = <ErrorState error={items.error} onRetry={() => items.refetch()} />;
  else if (items.data.length === 0) {
    content = view === 'active'
      ? <EmptyState title="Nothing needs attention" message="New items appear here when a milestone slips, work gets blocked, a budget runs over, or someone is booked past 8 hours." />
      : <EmptyState title="Nothing here yet" message="Items you resolve or dismiss are kept here with their notes." />;
  } else if (view === 'active') {
    content = (
      <Stack spacing={3}>
        {PRIORITIES.map((p) => {
          const group = items.data.filter((item) => item.priority === p.value);
          if (!group.length) return null;
          return (
            <Box key={p.value} component="section" aria-label={`${p.label} priority`}>
              <Typography variant="h3" component="h2" sx={{ mb: 1.5 }}>{p.label} <Typography component="span" color="text.secondary">{group.length}</Typography></Typography>
              <Stack spacing={1.5}>{group.map((item) => <ActionItem key={item.id} item={item} me={user} onClose={(it, status) => setClosing({ item: it, status })} />)}</Stack>
            </Box>
          );
        })}
      </Stack>
    );
  } else {
    content = <Stack spacing={1.5}>{items.data.map((item) => <ActionItem key={item.id} item={item} me={user} onClose={(it, status) => setClosing({ item: it, status })} />)}</Stack>;
  }

  const s = summary.data;
  return (
    <Stack spacing={3}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', gap: 2, flexWrap: 'wrap' }}>
        <Box>
          <Typography variant="h1">Action Center</Typography>
          <Typography color="text.secondary" sx={{ mt: 1, maxWidth: 720 }}>
            {s ? `${s.open_total} open, ${s.by_priority.critical} critical. ${s.resolved_this_week} resolved this week. ` : ''}
            Problems found in the data show up here on their own and close once they're fixed.
          </Typography>
        </Box>
        {canCreate && <Button variant="contained" startIcon={<AddRounded />} onClick={() => setCreating(true)}>New item</Button>}
      </Box>
      <ToggleButtonGroup size="small" exclusive value={view} onChange={(_, value) => value && setView(value)} aria-label="Show items">
        {VIEWS.map(([value, label]) => <ToggleButton key={value} value={value} sx={{ px: 2 }}>{label}</ToggleButton>)}
      </ToggleButtonGroup>
      <Box sx={{ opacity: items.isPlaceholderData ? 0.6 : 1 }}>{content}</Box>
      {closing && <CloseDialog item={closing.item} status={closing.status} onClose={() => setClosing(null)} />}
      {creating && <NewActionDialog me={user} onClose={() => setCreating(false)} />}
    </Stack>
  );
}