import { useState } from 'react';
import { Alert, Box, Button, MenuItem, Stack, TextField, Typography } from '@mui/material';
import FormDialog from '../FormDialog';
import useFormState from '../../hooks/useFormState';
import useApiMutation from '../../hooks/useApiMutation';
import { api } from '../../services/api';
import { formatDate, parseDate, toIsoDate } from '../../utils/format';

const joinNames = (names) => (names.length <= 1 ? names.join('') : `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`);

function defaultDates(project) {
  const today = new Date();
  const start = parseDate(project.start_date) > today ? parseDate(project.start_date) : today;
  const end = new Date(start);
  end.setDate(end.getDate() + 14);
  const projectEnd = parseDate(project.end_date);
  return { start_date: toIsoDate(start > projectEnd ? projectEnd : start), end_date: toIsoDate(end > projectEnd ? projectEnd : end) };
}

/**
 * Add a milestone, or edit and reschedule one. Moving dates requires a reason, and the app previews
 * any later milestones that would have to shift before anything is saved. If the shift would run past
 * the project's end date, the manager can extend the project in the same step.
 */
export default function MilestoneDialog({ project, milestones, milestone, onClose }) {
  const editing = Boolean(milestone);
  const form = useFormState(editing
    ? { name: milestone.name, description: milestone.description || '', start_date: milestone.start_date, end_date: milestone.end_date, change_reason: '', depends_on: [] }
    : { name: '', description: '', ...defaultDates(project), change_reason: '', depends_on: [] });
  const [preview, setPreview] = useState(null);
  const [overflow, setOverflow] = useState(null);
  const values = form.values;
  const datesChanged = editing && (values.start_date !== milestone.start_date || values.end_date !== milestone.end_date);
  const others = milestones.filter((m) => !editing || m.id !== milestone.id);
  const names = Object.fromEntries(others.map((m) => [m.id, m.name]));

  const save = useApiMutation(
    (body) => (editing ? api.put(`milestones/${milestone.id}`, body) : api.post('milestones', body)),
    {
      success: (data) => (editing
        ? `Saved ${data.name}.${data.shifted?.length ? ` ${data.shifted.length} later milestone(s) moved with it.` : ''}`
        : `Added ${data.name}.`),
      onSuccess: onClose,
      onError: form.fail,
    },
  );
  const dryRun = useApiMutation((body) => api.put(`milestones/${milestone.id}`, body), { onError: form.fail });
  const extendProject = useApiMutation((body) => api.put(`projects/${project.id}`, body), { onError: form.fail });
  const busy = save.isPending || dryRun.isPending || extendProject.isPending;

  const dateField = (name) => ({
    ...form.field(name),
    onChange: (event) => { form.set(name, event.target.value); setPreview(null); setOverflow(null); },
  });

  const baseBody = () => ({
    name: values.name.trim(), description: values.description.trim() || null, start_date: values.start_date, end_date: values.end_date,
  });

  async function submit() {
    const ok = form.check({
      name: !values.name.trim() && 'Enter a name.',
      start_date: !values.start_date && 'Choose a start date.',
      end_date: !values.end_date ? 'Choose a due date.' : values.end_date < values.start_date && 'Must be on or after the start date.',
      change_reason: datesChanged && !values.change_reason.trim() && 'Explain why the dates are moving.',
    });
    if (!ok) return;
    const body = baseBody();

    if (!editing) {
      save.mutate({ ...body, project_id: project.id, ...(values.depends_on.length ? { depends_on: values.depends_on } : {}) });
      return;
    }
    if (datesChanged) body.change_reason = values.change_reason.trim();
    if (datesChanged && !preview) {
      let result;
      try {
        result = await dryRun.mutateAsync({ ...body, dry_run: true });
      } catch {
        return;
      }
      if (result.overflows_project.length) {
        const neededEnd = result.shifted.reduce((latest, p) => (p.new_end > latest ? p.new_end : latest), project.end_date);
        setOverflow({ names: result.overflows_project, neededEnd, shifted: result.shifted });
        return;
      }
      if (result.shifted.length) {
        setPreview(result.shifted);
        return;
      }
    }
    save.mutate(preview ? { ...body, shift_dependents: true } : body);
  }

  /** Extends the project just enough to fit, records why in its history, then saves the move. */
  async function extendAndSave() {
    const reason = values.change_reason.trim();
    try {
      await extendProject.mutateAsync({
        end_date: overflow.neededEnd,
        change_reason: `Extended so ${joinNames(overflow.names)} still fit after ${milestone.name} moved: ${reason}`,
      });
    } catch {
      return;
    }
    save.mutate({ ...baseBody(), change_reason: reason, shift_dependents: true });
  }

  const dateSlots = { inputLabel: { shrink: true }, htmlInput: { min: project.start_date, max: project.end_date } };
  let submitLabel = editing ? 'Save changes' : 'Add milestone';
  if (preview) submitLabel = `Save and move ${preview.length} more`;

  return (
    <FormDialog title={editing ? `Edit ${milestone.name}` : 'Add milestone'} submitLabel={submitLabel}
      busy={busy} error={form.formError} onSubmit={submit} onClose={onClose}>
      {overflow && (
        <Alert severity="warning"
          action={(
            <Button color="inherit" size="small" onClick={extendAndSave} disabled={busy} sx={{ whiteSpace: 'nowrap', alignSelf: 'center' }}>
              Extend to {formatDate(overflow.neededEnd)} and save
            </Button>
          )}>
          <strong>Moving this would push {joinNames(overflow.names)} past the project end date ({formatDate(project.end_date)}).</strong>
          {' '}You can extend the project to {formatDate(overflow.neededEnd)} in the same step. Both changes are saved to the history with your reason.
          <Box component="ul" sx={{ m: 0, mt: 1, pl: 2.5 }}>
            {overflow.shifted.map((p) => (
              <li key={p.id}>{p.name}: {formatDate(p.old_start)} to {formatDate(p.old_end)} becomes {formatDate(p.new_start)} to {formatDate(p.new_end)}</li>
            ))}
          </Box>
        </Alert>
      )}
      <TextField label="Name" required autoFocus {...form.field('name')} />
      <Box>
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
          <TextField label="Start date" type="date" required {...dateField('start_date')} slotProps={dateSlots} />
          <TextField label="Due date" type="date" required {...dateField('end_date')} slotProps={dateSlots} />
        </Stack>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
          Must fall within the project, {formatDate(project.start_date)} to {formatDate(project.end_date)}.
        </Typography>
      </Box>
      {!editing && others.length > 0 && (
        <TextField select label="Waits for" value={values.depends_on} onChange={(event) => form.set('depends_on', event.target.value)}
          error={Boolean(form.errors.depends_on)}
          helperText={form.errors.depends_on || "It can't start until these are done, and must start on or after they end."}
          slotProps={{ select: { multiple: true, renderValue: (selected) => selected.map((id) => names[id]).join(', ') } }}>
          {others.map((m) => <MenuItem key={m.id} value={m.id}>{m.name} (due {formatDate(m.end_date)})</MenuItem>)}
        </TextField>
      )}
      {datesChanged && (
        <TextField label="Why are the dates changing?" required multiline minRows={2}
          {...form.field('change_reason', 'Saved to the project history so everyone can see why.')} />
      )}
      {preview && (
        <Alert severity="warning">
          <strong>These later milestones will move too, so they still start after this one ends:</strong>
          <Box component="ul" sx={{ m: 0, mt: 1, pl: 2.5 }}>
            {preview.map((p) => (
              <li key={p.id}>{p.name}: {formatDate(p.old_start)} to {formatDate(p.old_end)} becomes {formatDate(p.new_start)} to {formatDate(p.new_end)}</li>
            ))}
          </Box>
        </Alert>
      )}
      <TextField label="Description" multiline minRows={2} {...form.field('description')} />
    </FormDialog>
  );
}