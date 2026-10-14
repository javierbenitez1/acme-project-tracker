import { MenuItem, TextField } from '@mui/material';
import FormDialog from '../FormDialog';
import useFormState from '../../hooks/useFormState';
import useApiMutation from '../../hooks/useApiMutation';
import { api } from '../../services/api';
import { formatDate } from '../../utils/format';

/** Add or edit a deliverable inside a milestone (managers). */
export default function DeliverableDialog({ project, milestone, item, onClose }) {
  const editing = Boolean(item);
  const form = useFormState({
    title: item?.title || '', assignee_id: item?.assignee_id ?? '', due_date: item?.due_date || '', description: item?.description || '',
  });
  const people = project.members.filter((m) => m.role === 'employee');
  const values = form.values;

  const save = useApiMutation(
    (body) => (editing ? api.put(`deliverables/${item.id}`, body) : api.post('deliverables', { ...body, milestone_id: milestone.id })),
    { success: (data) => (editing ? `Saved ${data.title}.` : `Added ${data.title}.`), onSuccess: onClose, onError: form.fail },
  );

  function submit() {
    const outside = values.due_date && (values.due_date < milestone.start_date || values.due_date > milestone.end_date);
    const ok = form.check({
      title: !values.title.trim() && 'Enter what needs to be delivered.',
      due_date: outside && `Must fall within the milestone, ${formatDate(milestone.start_date)} to ${formatDate(milestone.end_date)}.`,
    });
    if (!ok) return;
    save.mutate({
      title: values.title.trim(),
      description: values.description.trim() || null,
      assignee_id: values.assignee_id === '' ? null : Number(values.assignee_id),
      due_date: values.due_date || null,
    });
  }

  return (
    <FormDialog title={editing ? `Edit ${item.title}` : `Add a deliverable to ${milestone.name}`}
      submitLabel={editing ? 'Save changes' : 'Add deliverable'} busy={save.isPending} error={form.formError} onSubmit={submit} onClose={onClose}>
      <TextField label="What needs to be delivered" required autoFocus {...form.field('title')} />
      <TextField select label="Assigned to" {...form.field('assignee_id', 'They can update its status from My work.')}>
        <MenuItem value="">Unassigned</MenuItem>
        {people.map((person) => <MenuItem key={person.id} value={person.id}>{person.name}</MenuItem>)}
      </TextField>
      <TextField label="Due date" type="date" {...form.field('due_date')}
        slotProps={{ inputLabel: { shrink: true }, htmlInput: { min: milestone.start_date, max: milestone.end_date } }} />
      <TextField label="Notes" multiline minRows={2} {...form.field('description')} />
    </FormDialog>
  );
}

/** Marking work as blocked always asks what's blocking it, so the manager can act on it. */
export function BlockedNoteDialog({ item, onClose }) {
  const form = useFormState({ status_note: item.status_note || '' });
  const save = useApiMutation((body) => api.put(`deliverables/${item.id}`, body), {
    success: `Marked ${item.title} as blocked. It now shows in the Action Center for the project manager.`,
    onSuccess: onClose,
    onError: form.fail,
  });
  function submit() {
    const note = form.values.status_note.trim();
    if (!form.check({ status_note: !note && 'Say what is blocking it.' })) return;
    save.mutate({ status: 'blocked', status_note: note });
  }
  return (
    <FormDialog title={`What's blocking ${item.title}?`} submitLabel="Mark as blocked" busy={save.isPending}
      error={form.formError} onSubmit={submit} onClose={onClose}>
      <TextField label="What's blocking it" required multiline minRows={3} autoFocus
        {...form.field('status_note', 'Be specific, like who or what you are waiting on.')} />
    </FormDialog>
  );
}