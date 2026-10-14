import { useState } from 'react';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import {
  Avatar, Box, Button, Card, Chip, IconButton, InputAdornment, MenuItem, Skeleton, Stack, Table, TableBody, TableCell,
  TableHead, TableRow, TextField, ToggleButton, ToggleButtonGroup, Tooltip, Typography,
} from '@mui/material';
import AddRounded from '@mui/icons-material/AddRounded';
import EditOutlined from '@mui/icons-material/EditOutlined';
import PersonOffOutlined from '@mui/icons-material/PersonOffOutlined';
import RestartAltRounded from '@mui/icons-material/RestartAltRounded';
import SearchRounded from '@mui/icons-material/SearchRounded';
import { useAuth } from '../auth/AuthContext';
import { api } from '../services/api';
import useDebounce from '../hooks/useDebounce';
import useFormState from '../hooks/useFormState';
import useApiMutation from '../hooks/useApiMutation';
import FormDialog from '../components/FormDialog';
import { ApiDeleteDialog } from '../components/ConfirmDialog';
import { EmptyState, ErrorState } from '../components/PageState';
import { ROLE_LABELS } from '../navigation';
import { initials } from '../utils/format';

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$/;
const USERNAME_RE = /^[A-Za-z0-9._-]{3,50}$/;
const passwordProblem = (pw) => (pw.length < 8 || !/[A-Za-z]/.test(pw) || !/\d/.test(pw)) && 'Use at least 8 characters with a letter and a number.';

function PersonDialog({ me, person, onClose }) {
  const editing = Boolean(person);
  const isAdmin = me.role === 'admin';
  const form = useFormState(editing
    ? { name: person.name, email: person.email, job_title: person.job_title || '', role: person.role, manager_id: person.manager_id ?? '', password: '' }
    : { username: '', password: '', name: '', email: '', job_title: '', role: 'employee', manager_id: '' });
  const values = form.values;
  const managers = useQuery({ queryKey: ['users', 'managers'], queryFn: () => api.get('users?role=manager'), enabled: isAdmin });
  const save = useApiMutation((body) => (editing ? api.put(`users/${person.id}`, body) : api.post('users', body)), {
    success: (data) => (editing ? `Saved ${data.name}.` : `Added ${data.name}. They can sign in as ${data.username}.`),
    onSuccess: onClose,
    onError: form.fail,
  });

  function submit() {
    const ok = form.check({
      username: !editing && !USERNAME_RE.test(values.username.trim()) && 'Use 3 to 50 letters, numbers, dots, dashes or underscores.',
      password: (!editing || values.password) && passwordProblem(values.password),
      name: !values.name.trim() && 'Enter their name.',
      email: !EMAIL_RE.test(values.email.trim()) && 'Enter a valid email address.',
      manager_id: isAdmin && values.role === 'employee' && !values.manager_id && 'Choose who they report to.',
    });
    if (!ok) return;
    const managerId = values.role === 'employee' && values.manager_id !== '' ? Number(values.manager_id) : null;
    if (!editing) {
      save.mutate({
        username: values.username.trim(), password: values.password, name: values.name.trim(), email: values.email.trim(),
        job_title: values.job_title.trim() || null, role: values.role, manager_id: managerId,
      });
      return;
    }
    const next = { name: values.name.trim(), email: values.email.trim().toLowerCase(), job_title: values.job_title.trim() || null };
    if (isAdmin) Object.assign(next, { role: values.role, manager_id: managerId });
    const body = Object.fromEntries(Object.entries(next).filter(([key, value]) => (person[key] ?? null) !== value));
    if (isAdmin && values.password) body.password = values.password;
    if (!Object.keys(body).length) {
      form.setFormError('Nothing has changed.');
      return;
    }
    save.mutate(body);
  }

  return (
    <FormDialog title={editing ? `Edit ${person.name}` : 'Add a person'} submitLabel={editing ? 'Save changes' : 'Add person'}
      busy={save.isPending} error={form.formError} onSubmit={submit} onClose={onClose}>
      {!editing && (
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
          <TextField label="Username" required autoFocus {...form.field('username', 'What they sign in with.')} />
          <TextField label="Temporary password" type="password" required {...form.field('password', 'At least 8 characters, with a letter and a number.')} />
        </Stack>
      )}
      <TextField label="Full name" required autoFocus={editing} {...form.field('name')} />
      <TextField label="Email" type="email" required {...form.field('email')} />
      <TextField label="Job title" {...form.field('job_title')} />
      {isAdmin && (
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
          <TextField select label="Role" {...form.field('role', editing ? 'Managers with active projects or reports must hand them over first.' : undefined)}>
            {['employee', 'manager', 'admin'].map((r) => <MenuItem key={r} value={r}>{ROLE_LABELS[r]}</MenuItem>)}
          </TextField>
          {values.role === 'employee' && (
            <TextField select label="Reports to" required {...form.field('manager_id')}>
              {(managers.data || []).map((m) => <MenuItem key={m.id} value={m.id}>{m.name}</MenuItem>)}
            </TextField>
          )}
        </Stack>
      )}
      {editing && isAdmin && (
        <TextField label="New password" type="password" {...form.field('password', 'Optional. Setting one signs them out everywhere.')} />
      )}
    </FormDialog>
  );
}

export default function PeoplePage() {
  const { user } = useAuth();
  const isAdmin = user.role === 'admin';
  const [search, setSearch] = useState('');
  const [scope, setScope] = useState(isAdmin ? 'everyone' : 'team');
  const [status, setStatus] = useState('active');
  const [dialog, setDialog] = useState(null);
  const term = useDebounce(search.trim(), 300);

  const params = new URLSearchParams({ status: isAdmin ? status : 'active' });
  if (term) params.set('search', term);
  if (scope === 'team') params.set('manager_id', user.id);
  const people = useQuery({ queryKey: ['users', 'list', params.toString()], queryFn: () => api.get(`users?${params}`), placeholderData: keepPreviousData });
  const reactivate = useApiMutation((person) => api.put(`users/${person.id}`, { is_active: true }), { success: (data) => `${data.name} can sign in again.` });
  const canEdit = (person) => isAdmin || person.manager_id === user.id;

  return (
    <Stack spacing={3}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', gap: 2, flexWrap: 'wrap' }}>
        <Box>
          <Typography variant="h1">People</Typography>
          <Typography color="text.secondary" sx={{ mt: 1 }}>
            {isAdmin ? 'Everyone at ACME. Add people, change roles, and decide who reports to whom.' : 'Your direct reports, plus everyone you can staff onto your projects. You can edit your direct reports.'}
          </Typography>
        </Box>
        {isAdmin && <Button variant="contained" startIcon={<AddRounded />} onClick={() => setDialog({ type: 'edit' })}>Add person</Button>}
      </Box>

      <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'center' }}>
        <TextField size="small" fullWidth={false} placeholder="Search by name, username, email or title" value={search}
          onChange={(event) => setSearch(event.target.value)} sx={{ flex: '1 1 280px', maxWidth: 440 }}
          slotProps={{ input: { startAdornment: <InputAdornment position="start"><SearchRounded fontSize="small" /></InputAdornment> }, htmlInput: { 'aria-label': 'Search people' } }} />
        {!isAdmin && (
          <ToggleButtonGroup size="small" exclusive value={scope} onChange={(_, value) => value && setScope(value)} aria-label="Whose people">
            <ToggleButton value="team" sx={{ px: 2 }}>My team</ToggleButton>
            <ToggleButton value="everyone" sx={{ px: 2 }}>Everyone</ToggleButton>
          </ToggleButtonGroup>
        )}
        {isAdmin && (
          <ToggleButtonGroup size="small" exclusive value={status} onChange={(_, value) => value && setStatus(value)} aria-label="Account status">
            <ToggleButton value="active" sx={{ px: 2 }}>Active</ToggleButton>
            <ToggleButton value="inactive" sx={{ px: 2 }}>Deactivated</ToggleButton>
            <ToggleButton value="all" sx={{ px: 2 }}>All</ToggleButton>
          </ToggleButtonGroup>
        )}
      </Box>

      {people.isPending ? <Skeleton variant="rounded" height={360} />
        : people.isError ? <ErrorState error={people.error} onRetry={() => people.refetch()} />
          : people.data.length === 0 ? <EmptyState title="No one matches" message="Try a different search or filter." />
            : (
              <Card sx={{ opacity: people.isPlaceholderData ? 0.6 : 1 }}>
                <Box sx={{ overflowX: 'auto' }}>
                  <Table aria-label="People">
                    <TableHead>
                      <TableRow>
                        <TableCell>Person</TableCell>
                        <TableCell>Role</TableCell>
                        <TableCell>Reports to</TableCell>
                        <TableCell align="right">Active projects</TableCell>
                        <TableCell align="right"><Box component="span" sx={{ position: 'absolute', left: -9999 }}>Actions</Box></TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {people.data.map((person) => (
                        <TableRow key={person.id} hover sx={{ opacity: person.is_active ? 1 : 0.6 }}>
                          <TableCell>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                              <Avatar sx={{ width: 36, height: 36, bgcolor: 'primary.main', color: 'primary.contrastText', fontSize: '0.85rem', fontWeight: 700 }}>{initials(person.name)}</Avatar>
                              <Box sx={{ minWidth: 0 }}>
                                <Typography sx={{ fontWeight: 600 }}>{person.name}{person.id === user.id ? ' (you)' : ''}</Typography>
                                <Typography variant="body2" color="text.secondary">{person.job_title || person.email}</Typography>
                              </Box>
                            </Box>
                          </TableCell>
                          <TableCell>
                            <Stack direction="row" spacing={1}>
                              <Chip size="small" label={ROLE_LABELS[person.role]} color={person.role === 'employee' ? 'default' : 'primary'} variant="outlined" />
                              {!person.is_active && <Chip size="small" label="Deactivated" />}
                            </Stack>
                          </TableCell>
                          <TableCell>{person.manager_name || <Typography component="span" color="text.secondary">None</Typography>}</TableCell>
                          <TableCell align="right">{person.active_projects}</TableCell>
                          <TableCell align="right" sx={{ whiteSpace: 'nowrap' }}>
                            {canEdit(person) && person.is_active && (
                              <Tooltip title="Edit">
                                <IconButton size="small" aria-label={`Edit ${person.name}`} onClick={() => setDialog({ type: 'edit', person })}><EditOutlined fontSize="small" /></IconButton>
                              </Tooltip>
                            )}
                            {isAdmin && person.id !== user.id && person.is_active && (
                              <Tooltip title="Deactivate">
                                <IconButton size="small" aria-label={`Deactivate ${person.name}`} onClick={() => setDialog({ type: 'deactivate', person })}><PersonOffOutlined fontSize="small" /></IconButton>
                              </Tooltip>
                            )}
                            {isAdmin && !person.is_active && (
                              <Button size="small" startIcon={<RestartAltRounded />} onClick={() => reactivate.mutate(person)} disabled={reactivate.isPending}>Reactivate</Button>
                            )}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </Box>
              </Card>
            )}

      {dialog?.type === 'edit' && <PersonDialog me={user} person={dialog.person} onClose={() => setDialog(null)} />}
      {dialog?.type === 'deactivate' && (
        <ApiDeleteDialog title={`Deactivate ${dialog.person.name}?`} confirmLabel="Deactivate"
          message="They're signed out everywhere and can't sign in. Their history stays. Managers must hand over their projects and reports first. You can reactivate them later."
          path={`users/${dialog.person.id}`} success={`Deactivated ${dialog.person.name}.`} onClose={() => setDialog(null)} />
      )}
    </Stack>
  );
}