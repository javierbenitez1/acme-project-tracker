import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Box, Button, Card, CardContent, Chip, IconButton, LinearProgress, Menu, MenuItem, Skeleton, Stack, TextField,
  Tooltip, Typography,
} from '@mui/material';
import AddRounded from '@mui/icons-material/AddRounded';
import CheckRounded from '@mui/icons-material/CheckRounded';
import DeleteOutlineRounded from '@mui/icons-material/DeleteOutlineRounded';
import EditOutlined from '@mui/icons-material/EditOutlined';
import MoreVertRounded from '@mui/icons-material/MoreVertRounded';
import { useAuth } from '../../auth/AuthContext';
import { api } from '../../services/api';
import useApiMutation from '../../hooks/useApiMutation';
import { ApiDeleteDialog } from '../ConfirmDialog';
import { EmptyState } from '../PageState';
import { healthText } from '../HealthChip';
import MilestoneDialog from './MilestoneDialog';
import AssignDialog from './AssignDialog';
import DeliverableDialog, { BlockedNoteDialog } from './DeliverableDialog';
import { formatDate, formatDue, parseDate } from '../../utils/format';

const MILESTONE_STATUS = [['not_started', 'Not started'], ['in_progress', 'In progress'], ['blocked', 'Blocked'], ['done', 'Done']];
const WORK_STATUS = [['todo', 'To do'], ['in_progress', 'In progress'], ['blocked', 'Blocked'], ['done', 'Done']];
const labelOf = (pairs, value) => pairs.find(([key]) => key === value)?.[1] || value;

function StatusSelect({ value, options, onChange, disabled, label }) {
  return (
    <TextField select size="small" fullWidth={false} value={value} disabled={disabled}
      onChange={(event) => onChange(event.target.value)} sx={{ minWidth: 150 }}
      slotProps={{ select: { SelectDisplayProps: { 'aria-label': label } } }}>
      {options.map(([key, text]) => <MenuItem key={key} value={key}>{text}</MenuItem>)}
    </TextField>
  );
}

function DeliverableRow({ item, canManage, userId, milestoneDone, openDialog }) {
  const mine = item.assignee_id === userId;
  const canSetStatus = (canManage || mine) && !milestoneDone;
  const setStatus = useApiMutation((status) => api.put(`deliverables/${item.id}`, { status }), {
    success: (data) => {
      if (data.milestone_ready) return `Done. Every deliverable in ${data.milestone_name} is finished, so it's ready to close.`;
      if (data.milestone_started) return `${data.milestone_name} has started.`;
      return `${data.title} is now ${labelOf(WORK_STATUS, data.status).toLowerCase()}.`;
    },
  });
  const changeStatus = (status) => (status === 'blocked' ? openDialog({ type: 'blocked', item }) : setStatus.mutate(status));

  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, py: 1.25, borderTop: 1, borderColor: 'divider', flexWrap: { xs: 'wrap', sm: 'nowrap' } }}>
      <Box sx={{ flexGrow: 1, minWidth: 0 }}>
        <Typography sx={{ fontWeight: 500, color: item.status === 'done' ? 'text.secondary' : 'text.primary' }}>{item.title}</Typography>
        <Typography variant="body2" color="text.secondary">
          {item.assignee_name ? `${item.assignee_name}${mine ? ' (you)' : ''}` : 'Unassigned'}
          {item.due_date && item.status !== 'done' && (
            <Box component="span" sx={item.is_overdue ? healthText('off_track') : undefined}>, {formatDue(item.due_date).toLowerCase()}</Box>
          )}
        </Typography>
        {item.status === 'blocked' && item.status_note && (
          <Typography variant="body2" sx={[{ mt: 0.5 }, ...healthText('off_track')]}>Blocked: {item.status_note}</Typography>
        )}
      </Box>
      {canSetStatus ? (
        <StatusSelect value={item.status} options={WORK_STATUS} onChange={changeStatus} disabled={setStatus.isPending} label={`Status of ${item.title}`} />
      ) : (
        <Chip size="small" variant="outlined" label={labelOf(WORK_STATUS, item.status)} />
      )}
      {canManage && (
        <Box sx={{ display: 'flex' }}>
          <Tooltip title="Edit deliverable">
            <IconButton size="small" aria-label={`Edit ${item.title}`} onClick={() => openDialog({ type: 'deliverable', item })}><EditOutlined fontSize="small" /></IconButton>
          </Tooltip>
          <Tooltip title="Remove deliverable">
            <IconButton size="small" aria-label={`Remove ${item.title}`} onClick={() => openDialog({ type: 'deleteDeliverable', item })}><DeleteOutlineRounded fontSize="small" /></IconButton>
          </Tooltip>
        </Box>
      )}
    </Box>
  );
}

function MilestoneCard({ milestone: m, milestones, deliverables, canManage, userId, openDialog }) {
  const [menuAnchor, setMenuAnchor] = useState(null);
  const [dependencyAnchor, setDependencyAnchor] = useState(null);
  const setStatus = useApiMutation((status) => api.put(`milestones/${m.id}`, { status }), {
    success: (data) => `${data.name} is now ${labelOf(MILESTONE_STATUS, data.status).toLowerCase()}.`,
  });
  const addDependency = useApiMutation((id) => api.post(`milestones/${m.id}/dependencies`, { depends_on_id: id }), { success: 'Dependency added.' });
  const removeDependency = useApiMutation((id) => api.delete(`milestones/${m.id}/dependencies/${id}`), { success: 'Dependency removed.' });
  const unassign = useApiMutation((userIdToRemove) => api.delete(`milestones/${m.id}/assignments/${userIdToRemove}`), { success: 'Removed from the milestone.' });

  const done = m.status === 'done';
  const eligible = milestones.filter((other) => other.id !== m.id && !m.depends_on.includes(other.id));
  const open = (dialog) => openDialog({ milestone: m, ...dialog });

  return (
    <Card component="article" aria-label={m.name}>
      <CardContent sx={{ p: { xs: 2, md: 3 }, '&:last-child': { pb: { xs: 2, md: 3 } } }}>
        <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 2, flexWrap: 'wrap' }}>
          <Box sx={{ flexGrow: 1, minWidth: 220 }}>
            <Typography variant="h3" component="h2">{m.name}</Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.25 }}>
              {formatDate(m.start_date)} to {formatDate(m.end_date)}
              {!done && <Box component="span" sx={m.is_overdue ? healthText('off_track') : undefined}>, {formatDue(m.end_date).toLowerCase()}</Box>}
            </Typography>
          </Box>
          {canManage ? (
            <StatusSelect value={m.status} options={MILESTONE_STATUS} onChange={(status) => setStatus.mutate(status)} disabled={setStatus.isPending} label={`Status of ${m.name}`} />
          ) : (
            <Chip variant="outlined" label={labelOf(MILESTONE_STATUS, m.status)} />
          )}
          {canManage && (
            <>
              <IconButton aria-label={`More actions for ${m.name}`} aria-haspopup="menu" onClick={(event) => setMenuAnchor(event.currentTarget)}>
                <MoreVertRounded />
              </IconButton>
              <Menu anchorEl={menuAnchor} open={Boolean(menuAnchor)} onClose={() => setMenuAnchor(null)}>
                <MenuItem onClick={() => { setMenuAnchor(null); open({ type: 'milestone' }); }}>Edit or reschedule</MenuItem>
                <MenuItem onClick={() => { setMenuAnchor(null); open({ type: 'deleteMilestone' }); }} sx={{ color: 'error.main' }}>Delete milestone</MenuItem>
              </Menu>
            </>
          )}
        </Box>

        {m.description && <Typography color="text.secondary" sx={{ mt: 1.5, maxWidth: 760 }}>{m.description}</Typography>}

        <Box sx={{ mt: 2 }}>
          <LinearProgress variant="determinate" value={m.progress} sx={{ height: 6, borderRadius: 3 }} aria-label={`${m.name}: ${m.progress}% complete`} />
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.75 }}>
            {m.deliverables_done} of {m.deliverables_total} deliverables done
          </Typography>
        </Box>

        <Stack spacing={1.5} sx={{ mt: 2.5 }}>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 1 }}>
            <Typography variant="body2" sx={{ fontWeight: 600, minWidth: 80 }}>Waits for</Typography>
            {m.dependencies.length === 0 && <Typography variant="body2" color="text.secondary">Nothing, it can start any time</Typography>}
            {m.dependencies.map((dependency) => (
              <Chip key={dependency.id} size="small" label={dependency.name}
                icon={dependency.status === 'done' ? <CheckRounded /> : undefined}
                color={dependency.status === 'done' ? 'primary' : 'default'} variant="outlined"
                onDelete={canManage && !done ? () => removeDependency.mutate(dependency.id) : undefined} />
            ))}
            {canManage && !done && eligible.length > 0 && (
              <>
                <Button size="small" startIcon={<AddRounded />} onClick={(event) => setDependencyAnchor(event.currentTarget)}>Add</Button>
                <Menu anchorEl={dependencyAnchor} open={Boolean(dependencyAnchor)} onClose={() => setDependencyAnchor(null)}>
                  {eligible.map((other) => (
                    <MenuItem key={other.id} onClick={() => { setDependencyAnchor(null); addDependency.mutate(other.id); }}>
                      {other.name} (due {formatDate(other.end_date)})
                    </MenuItem>
                  ))}
                </Menu>
              </>
            )}
          </Box>

          <Box sx={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 1 }}>
            <Typography variant="body2" sx={{ fontWeight: 600, minWidth: 80 }}>Team</Typography>
            {m.assignees.length === 0 && <Typography variant="body2" color="text.secondary">No one is booked yet</Typography>}
            {m.assignees.map((person) => (
              <Chip key={person.user_id} size="small" label={`${person.name}, ${Number(person.hours_per_day)}h/day`}
                onClick={canManage && !done ? () => open({ type: 'assign', assignee: person }) : undefined}
                onDelete={canManage && !done ? () => unassign.mutate(person.user_id) : undefined} />
            ))}
            {canManage && !done && <Button size="small" startIcon={<AddRounded />} onClick={() => open({ type: 'assign' })}>Assign</Button>}
          </Box>
        </Stack>

        <Box sx={{ mt: 2.5 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 0.5 }}>
            <Typography variant="body2" sx={{ fontWeight: 600 }}>Deliverables</Typography>
            {canManage && !done && <Button size="small" startIcon={<AddRounded />} onClick={() => open({ type: 'deliverable' })}>Add deliverable</Button>}
          </Box>
          {deliverables.length === 0 ? (
            <Typography variant="body2" color="text.secondary" sx={{ py: 1 }}>No deliverables yet.</Typography>
          ) : deliverables.map((item) => (
            <DeliverableRow key={item.id} item={item} canManage={canManage} userId={userId} milestoneDone={done}
              openDialog={(dialog) => open(dialog)} />
          ))}
        </Box>
      </CardContent>
    </Card>
  );
}

export default function MilestonesTab({ project, milestones, loading }) {
  const { user } = useAuth();
  const [dialog, setDialog] = useState(null);
  const canManage = project.can_manage && !project.is_archived;
  const deliverables = useQuery({
    queryKey: ['deliverables', { project: project.id }],
    queryFn: () => api.get(`deliverables?project_id=${project.id}&include_archived=true`),
    refetchInterval: 30_000,
  });
  const sorted = [...milestones].sort((a, b) => parseDate(a.start_date) - parseDate(b.start_date) || a.id - b.id);
  const byMilestone = {};
  (deliverables.data || []).forEach((item) => { (byMilestone[item.milestone_id] ||= []).push(item); });
  const close = () => setDialog(null);
  const doneCount = sorted.filter((m) => m.status === 'done').length;

  return (
    <Stack spacing={2.5}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 2 }}>
        <Typography color="text.secondary">
          {canManage
            ? `${sorted.length} milestones, ${doneCount} done. Change a status, reschedule, or assign people right here.`
            : 'You can update the status of work assigned to you.'}
        </Typography>
        {canManage && <Button variant="contained" startIcon={<AddRounded />} onClick={() => setDialog({ type: 'milestone' })}>Add milestone</Button>}
      </Box>

      {loading || deliverables.isPending ? (
        <Stack spacing={2}>{[0, 1].map((i) => <Skeleton key={i} variant="rounded" height={260} />)}</Stack>
      ) : sorted.length === 0 ? (
        <EmptyState title="No milestones yet" message={canManage ? 'Break the project into milestones with their own dates, then add the work inside each one.' : 'Your manager hasn\'t added milestones yet.'}
          action={canManage ? <Button variant="contained" onClick={() => setDialog({ type: 'milestone' })}>Add the first milestone</Button> : null} />
      ) : sorted.map((m) => (
        <MilestoneCard key={m.id} milestone={m} milestones={sorted} deliverables={byMilestone[m.id] || []}
          canManage={canManage} userId={user.id} openDialog={setDialog} />
      ))}

      {dialog?.type === 'milestone' && <MilestoneDialog project={project} milestones={sorted} milestone={dialog.milestone} onClose={close} />}
      {dialog?.type === 'assign' && <AssignDialog project={project} milestone={dialog.milestone} assignee={dialog.assignee} onClose={close} />}
      {dialog?.type === 'deliverable' && <DeliverableDialog project={project} milestone={dialog.milestone} item={dialog.item} onClose={close} />}
      {dialog?.type === 'blocked' && <BlockedNoteDialog item={dialog.item} onClose={close} />}
      {dialog?.type === 'deleteMilestone' && (
        <ApiDeleteDialog title={`Delete ${dialog.milestone.name}?`}
          message="Its deliverables and assignments are removed too, and later milestones stop waiting on it. The deletion is recorded in the audit log."
          path={`milestones/${dialog.milestone.id}`} success={`Deleted ${dialog.milestone.name}.`} onClose={close} />
      )}
      {dialog?.type === 'deleteDeliverable' && (
        <ApiDeleteDialog title={`Remove ${dialog.item.title}?`} confirmLabel="Remove"
          message="The deliverable is removed from this milestone. The change is recorded in the audit log."
          path={`deliverables/${dialog.item.id}`} success="Deliverable removed." onClose={close} />
      )}
    </Stack>
  );
}