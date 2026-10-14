import { useState } from 'react';
import { Link as RouterLink, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  Box, Button, Card, CardContent, Skeleton, Stack, TextField, ToggleButton, ToggleButtonGroup, Typography,
} from '@mui/material';
import RestoreRounded from '@mui/icons-material/RestoreRounded';
import { api } from '../services/api';
import useFormState from '../hooks/useFormState';
import useApiMutation from '../hooks/useApiMutation';
import FormDialog from '../components/FormDialog';
import HealthChip from '../components/HealthChip';
import { EmptyState, ErrorState } from '../components/PageState';
import { formatDate, formatMoney } from '../utils/format';

function RestoreDialog({ project, onClose }) {
  const navigate = useNavigate();
  const form = useFormState({ reason: '' });
  const restore = useApiMutation((body) => api.post(`projects/${project.id}/restore`, body), {
    success: `Restored ${project.name}. It's active and editable again.`,
    onSuccess: () => { onClose(); navigate(`/projects/${project.id}`); },
    onError: form.fail,
  });
  return (
    <FormDialog title={`Restore ${project.name}?`} submitLabel="Restore project" busy={restore.isPending} error={form.formError}
      onSubmit={() => restore.mutate(form.values.reason.trim() ? { reason: form.values.reason.trim() } : {})} onClose={onClose}>
      <Typography color="text.secondary">
        {project.status === 'completed' ? 'It goes back to active so work can continue.' : 'It becomes active again, with its team, milestones and budget as they were.'}
      </Typography>
      <TextField label="Why is it coming back?" multiline minRows={2} autoFocus {...form.field('reason', 'Optional. Saved to the audit log.')} />
    </FormDialog>
  );
}

export default function ArchivePage() {
  const [filter, setFilter] = useState('all');
  const [restoring, setRestoring] = useState(null);
  const projects = useQuery({ queryKey: ['projects', 'archive'], queryFn: () => api.get('projects?archived=true&sort=end_date') });
  const shown = (projects.data || []).filter((p) => filter === 'all' || (filter === 'completed') === (p.status === 'completed'));

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h1">Archive</Typography>
        <Typography color="text.secondary" sx={{ mt: 1, maxWidth: 720 }}>
          Projects are never deleted. Completed and archived projects stay here, read-only, and can be restored.
        </Typography>
      </Box>
      <ToggleButtonGroup size="small" exclusive value={filter} onChange={(_, value) => value && setFilter(value)} aria-label="Show">
        <ToggleButton value="all" sx={{ px: 2 }}>All</ToggleButton>
        <ToggleButton value="completed" sx={{ px: 2 }}>Completed</ToggleButton>
        <ToggleButton value="archived" sx={{ px: 2 }}>Archived early</ToggleButton>
      </ToggleButtonGroup>

      {projects.isPending ? <Skeleton variant="rounded" height={300} />
        : projects.isError ? <ErrorState error={projects.error} onRetry={() => projects.refetch()} />
          : shown.length === 0 ? <EmptyState title="Nothing archived" message="Completed projects and projects an admin archives show up here." />
            : (
              <Stack spacing={2}>
                {shown.map((project) => (
                  <Card key={project.id}>
                    <CardContent sx={{ p: { xs: 2, md: 3 }, '&:last-child': { pb: { xs: 2, md: 3 } } }}>
                      <Box sx={{ display: 'flex', gap: 2, alignItems: 'flex-start', flexWrap: 'wrap' }}>
                        <Box sx={{ flexGrow: 1, minWidth: 240 }}>
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, flexWrap: 'wrap' }}>
                            <Typography variant="h3" component="h2">{project.name}</Typography>
                            <HealthChip value={project.health} size="small" />
                          </Box>
                          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                            {project.manager_name}{project.department ? `, ${project.department}` : ''}. {formatDate(project.start_date)} to {formatDate(project.end_date)}.
                          </Typography>
                          <Typography sx={{ mt: 1.5 }}>
                            {project.status === 'completed' ? 'Completed' : 'Archived'} on {formatDate(project.archived_at)}
                            {project.archive_reason ? `: ${project.archive_reason}` : '.'}
                          </Typography>
                          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                            {project.milestones_done} of {project.milestone_count} milestones done, {formatMoney(project.budget_spent)} of {formatMoney(project.budget_planned)} spent.
                          </Typography>
                        </Box>
                        <Stack direction="row" spacing={1}>
                          <Button component={RouterLink} to={`/projects/${project.id}`}>View</Button>
                          <Button variant="outlined" startIcon={<RestoreRounded />} onClick={() => setRestoring(project)}>Restore</Button>
                        </Stack>
                      </Box>
                    </CardContent>
                  </Card>
                ))}
              </Stack>
            )}
      {restoring && <RestoreDialog project={restoring} onClose={() => setRestoring(null)} />}
    </Stack>
  );
}