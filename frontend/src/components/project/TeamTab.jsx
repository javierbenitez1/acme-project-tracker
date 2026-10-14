import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Autocomplete, Avatar, Box, Button, Chip, IconButton, List, ListItem, ListItemAvatar, ListItemText, TextField, Tooltip,
  Typography,
} from '@mui/material';
import PersonAddAlt1Outlined from '@mui/icons-material/PersonAddAlt1Outlined';
import PersonRemoveOutlined from '@mui/icons-material/PersonRemoveOutlined';
import Section from '../Section';
import FormDialog from '../FormDialog';
import { ApiDeleteDialog } from '../ConfirmDialog';
import useApiMutation from '../../hooks/useApiMutation';
import { api } from '../../services/api';
import { describeError } from '../../utils/errors';
import { initials } from '../../utils/format';

function AddMembersDialog({ project, onClose }) {
  const people = useQuery({ queryKey: ['users', 'employees'], queryFn: () => api.get('users?role=employee') });
  const memberIds = new Set(project.members.map((m) => m.id));
  const options = (people.data || [])
    .filter((u) => !memberIds.has(u.id))
    .sort((a, b) => (a.manager_name || '').localeCompare(b.manager_name || '') || a.name.localeCompare(b.name));
  const [selected, setSelected] = useState([]);
  const [error, setError] = useState('');
  const add = useApiMutation((ids) => api.post(`projects/${project.id}/members`, { user_ids: ids }), {
    success: (_, ids) => `Added ${ids.length} ${ids.length === 1 ? 'person' : 'people'} to the team.`,
    onSuccess: onClose,
    onError: (err) => setError(describeError(err)),
  });

  function submit() {
    if (!selected.length) {
      setError('Choose at least one person.');
      return;
    }
    add.mutate(selected.map((u) => u.id));
  }

  return (
    <FormDialog title="Add people to the team" submitLabel="Add to team" busy={add.isPending} error={error} onSubmit={submit} onClose={onClose}>
      <Autocomplete
        multiple
        options={options}
        value={selected}
        onChange={(_, value) => { setSelected(value); setError(''); }}
        loading={people.isPending}
        getOptionLabel={(u) => u.name}
        isOptionEqualToValue={(a, b) => a.id === b.id}
        groupBy={(u) => (u.manager_name ? `Reports to ${u.manager_name}` : 'No manager')}
        renderOption={(props, u) => {
          const { key, ...rest } = props;
          return (
            <li key={key} {...rest}>
              <Box>
                <Typography>{u.name}</Typography>
                <Typography variant="body2" color="text.secondary">
                  {u.job_title || 'Employee'}{u.active_projects ? `, on ${u.active_projects} active project${u.active_projects === 1 ? '' : 's'}` : ''}
                </Typography>
              </Box>
            </li>
          );
        }}
        renderInput={(params) => (
          <TextField {...params} label="People" placeholder="Search by name" autoFocus
            helperText="Employees from any team can join. Who they report to doesn't change." />
        )}
      />
    </FormDialog>
  );
}

export default function TeamTab({ project, milestones }) {
  const canManage = project.can_manage && !project.is_archived;
  const [adding, setAdding] = useState(false);
  const [removing, setRemoving] = useState(null);

  return (
    <Section title="Team" subtitle="Everyone on this project and the open milestones they're booked on."
      action={canManage ? <Button startIcon={<PersonAddAlt1Outlined />} onClick={() => setAdding(true)}>Add people</Button> : null}>
      <List disablePadding>
        {project.members.map((member) => {
          const bookings = milestones
            .filter((m) => m.status !== 'done')
            .flatMap((m) => m.assignees.filter((a) => a.user_id === member.id).map((a) => `${m.name} (${Number(a.hours_per_day)}h/day)`));
          const detail = [
            member.job_title,
            bookings.length ? `Booked on ${bookings.join(', ')}` : !member.is_manager && 'Not booked on any open milestone',
          ].filter(Boolean).join('. ');
          return (
            <ListItem key={member.id} disableGutters divider
              secondaryAction={canManage && !member.is_manager ? (
                <Tooltip title="Remove from the project">
                  <IconButton edge="end" aria-label={`Remove ${member.name} from the project`} onClick={() => setRemoving(member)}>
                    <PersonRemoveOutlined />
                  </IconButton>
                </Tooltip>
              ) : null}>
              <ListItemAvatar>
                <Avatar sx={{
                  bgcolor: member.is_manager ? 'secondary.main' : 'primary.main',
                  color: member.is_manager ? 'secondary.contrastText' : 'primary.contrastText', fontWeight: 700, fontSize: '0.9rem',
                }}>
                  {initials(member.name)}
                </Avatar>
              </ListItemAvatar>
              <ListItemText
                slotProps={{ primary: { component: 'div' } }}
                primary={(
                  <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
                    <Typography sx={{ fontWeight: 600 }}>{member.name}</Typography>
                    {member.is_manager && <Chip size="small" label="Project manager" />}
                  </Box>
                )}
                secondary={detail}
              />
            </ListItem>
          );
        })}
      </List>
      {adding && <AddMembersDialog project={project} onClose={() => setAdding(false)} />}
      {removing && (
        <ApiDeleteDialog title={`Remove ${removing.name} from ${project.name}?`} confirmLabel="Remove"
          message="They lose access to this project. If they still have open work or bookings here, reassign those first."
          path={`projects/${project.id}/members/${removing.id}`} success={`Removed ${removing.name} from the team.`}
          onClose={() => setRemoving(null)} />
      )}
    </Section>
  );
}