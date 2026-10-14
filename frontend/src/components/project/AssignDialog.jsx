import { useState } from 'react';
import { Alert, Box, MenuItem, TextField } from '@mui/material';
import FormDialog from '../FormDialog';
import useFormState from '../../hooks/useFormState';
import useApiMutation from '../../hooks/useApiMutation';
import { api } from '../../services/api';
import { formatDate } from '../../utils/format';

/** Book someone onto a milestone for some hours a day. The server enforces the 8-hour workday. */
export default function AssignDialog({ project, milestone, assignee, onClose }) {
  const editing = Boolean(assignee);
  const taken = new Set(milestone.assignees.map((a) => a.user_id));
  const options = project.members.filter((m) => m.role === 'employee' && m.is_active && !taken.has(m.id));
  const form = useFormState({ user_id: assignee?.user_id ?? '', hours_per_day: assignee ? String(Number(assignee.hours_per_day)) : '8' });
  const [bookings, setBookings] = useState(null);
  const values = form.values;

  const save = useApiMutation(
    (body) => (editing
      ? api.put(`milestones/${milestone.id}/assignments/${assignee.user_id}`, { hours_per_day: body.hours_per_day })
      : api.post(`milestones/${milestone.id}/assignments`, body)),
    {
      success: editing ? `Updated ${assignee.name}'s hours.` : 'Assigned.',
      onSuccess: onClose,
      onError: (error) => { form.fail(error); setBookings(error.details?.booked_on || null); },
    },
  );

  function submit() {
    const hours = Number(values.hours_per_day);
    const ok = form.check({
      user_id: !editing && !values.user_id && 'Choose someone from the project team.',
      hours_per_day: !(hours >= 0.5 && hours <= 8) && 'Enter between 0.5 and 8 hours a day.',
    });
    if (!ok) return;
    setBookings(null);
    save.mutate({ user_id: Number(values.user_id), hours_per_day: hours });
  }

  return (
    <FormDialog title={editing ? `Change ${assignee.name}'s hours` : `Assign someone to ${milestone.name}`}
      submitLabel={editing ? 'Save hours' : 'Assign'} busy={save.isPending} error={form.formError} onSubmit={submit} onClose={onClose}>
      {!editing && options.length === 0 && (
        <Alert severity="info">Everyone on the team is already on this milestone. Add more people on the Team tab.</Alert>
      )}
      {!editing && options.length > 0 && (
        <TextField select label="Person" required {...form.field('user_id', 'Only people on the project team are listed.')}>
          {options.map((person) => (
            <MenuItem key={person.id} value={person.id}>{person.name}{person.job_title ? `, ${person.job_title}` : ''}</MenuItem>
          ))}
        </TextField>
      )}
      <TextField label="Hours per day" type="number" required
        {...form.field('hours_per_day', "A full workday is 8 hours. No one can be booked over 8 hours a day across all their milestones.")}
        slotProps={{ htmlInput: { min: 0.5, max: 8, step: 0.5 } }} />
      {bookings && bookings.length > 0 && (
        <Alert severity="warning">
          <strong>Already booked during these dates:</strong>
          <Box component="ul" sx={{ m: 0, mt: 1, pl: 2.5 }}>
            {bookings.map((b) => (
              <li key={`${b.project}-${b.milestone}`}>
                {b.milestone} ({b.project}), {Number(b.hours_per_day)}h/day, {formatDate(b.start_date)} to {formatDate(b.end_date)}
              </li>
            ))}
          </Box>
        </Alert>
      )}
    </FormDialog>
  );
}