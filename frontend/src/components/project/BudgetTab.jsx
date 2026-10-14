import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Box, Button, Card, Chip, IconButton, InputAdornment, LinearProgress, MenuItem, Skeleton, Stack, Table, TableBody,
  TableCell, TableHead, TableRow, TextField, Tooltip, Typography,
} from '@mui/material';
import AddRounded from '@mui/icons-material/AddRounded';
import DeleteOutlineRounded from '@mui/icons-material/DeleteOutlineRounded';
import EditOutlined from '@mui/icons-material/EditOutlined';
import TuneRounded from '@mui/icons-material/TuneRounded';
import Section from '../Section';
import FormDialog from '../FormDialog';
import { ApiDeleteDialog } from '../ConfirmDialog';
import { EmptyState, ErrorState } from '../PageState';
import { healthText } from '../HealthChip';
import BurnChart from './BurnChart';
import useFormState from '../../hooks/useFormState';
import useApiMutation from '../../hooks/useApiMutation';
import { api } from '../../services/api';
import { formatDate, formatMoney, toIsoDate } from '../../utils/format';

const CATEGORIES = ['labor', 'contractors', 'software', 'hardware', 'travel', 'training', 'other'];
const capitalize = (text) => text.charAt(0).toUpperCase() + text.slice(1);

function forecastText(forecast) {
  if (forecast.status === 'not_enough_data') return 'Not enough spending yet to forecast.';
  const gap = formatMoney(Math.abs(forecast.projected_variance));
  if (forecast.status === 'over') return `On pace to finish ${gap} over budget.`;
  if (forecast.status === 'under') return `On pace to finish ${gap} under budget.`;
  return 'On pace to land close to the plan.';
}

function SpendDialog({ project, entry, onClose }) {
  const editing = Boolean(entry);
  const form = useFormState({
    amount: entry ? String(entry.amount) : '', category: entry?.category || 'labor',
    entry_date: entry?.entry_date || toIsoDate(new Date()), description: entry?.description || '',
  });
  const values = form.values;
  const save = useApiMutation(
    (body) => (editing ? api.put(`budgets/${entry.id}`, body) : api.post('budgets', { ...body, project_id: project.id })),
    { success: (data) => `${editing ? 'Updated' : 'Recorded'} ${formatMoney(data.amount)} of ${data.category} spending.`, onSuccess: onClose, onError: form.fail },
  );
  const today = toIsoDate(new Date());
  function submit() {
    const amount = Number(values.amount);
    const ok = form.check({
      amount: !(amount > 0) && 'Enter an amount greater than 0.',
      entry_date: !values.entry_date ? 'Choose the date it was spent.'
        : values.entry_date > today ? "Spending can't be recorded in the future."
          : values.entry_date < project.start_date && `Must be on or after the project start (${formatDate(project.start_date)}).`,
    });
    if (!ok) return;
    save.mutate({ amount, category: values.category, entry_date: values.entry_date, description: values.description.trim() || null });
  }
  return (
    <FormDialog title={editing ? 'Edit spending' : 'Record spending'} submitLabel={editing ? 'Save changes' : 'Record spending'}
      busy={save.isPending} error={form.formError} onSubmit={submit} onClose={onClose}>
      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
        <TextField label="Amount" type="number" required autoFocus {...form.field('amount')}
          slotProps={{ input: { startAdornment: <InputAdornment position="start">$</InputAdornment> }, htmlInput: { min: 0.01, step: 100 } }} />
        <TextField select label="Category" required {...form.field('category')}>
          {CATEGORIES.map((c) => <MenuItem key={c} value={c}>{capitalize(c)}</MenuItem>)}
        </TextField>
      </Stack>
      <TextField label="Date spent" type="date" required {...form.field('entry_date')}
        slotProps={{ inputLabel: { shrink: true }, htmlInput: { min: project.start_date, max: today } }} />
      <TextField label="What it was for" {...form.field('description', 'For example, the vendor or the sprint it paid for.')} />
    </FormDialog>
  );
}

function AdjustBudgetDialog({ project, onClose }) {
  const form = useFormState({ budget_planned: String(project.budget_planned), change_reason: '' });
  const save = useApiMutation((body) => api.put(`projects/${project.id}`, body), {
    success: (data) => `Planned budget is now ${formatMoney(data.budget_planned)}.`, onSuccess: onClose, onError: form.fail,
  });
  function submit() {
    const amount = Number(form.values.budget_planned);
    const ok = form.check({
      budget_planned: !(amount >= 0) ? 'Enter an amount of 0 or more.' : amount === Number(project.budget_planned) && 'Enter a different amount.',
      change_reason: !form.values.change_reason.trim() && 'Explain why the budget is changing.',
    });
    if (!ok) return;
    save.mutate({ budget_planned: amount, change_reason: form.values.change_reason.trim() });
  }
  return (
    <FormDialog title="Adjust the planned budget" submitLabel="Save budget" busy={save.isPending} error={form.formError} onSubmit={submit} onClose={onClose}>
      <TextField label="New planned budget" type="number" required autoFocus
        {...form.field('budget_planned', `Currently ${formatMoney(project.budget_planned)}.`)}
        slotProps={{ input: { startAdornment: <InputAdornment position="start">$</InputAdornment> }, htmlInput: { min: 0, step: 1000 } }} />
      <TextField label="Why is it changing?" required multiline minRows={2}
        {...form.field('change_reason', 'Saved to the project history with your name.')} />
    </FormDialog>
  );
}

export default function BudgetTab({ project }) {
  const canManage = project.can_manage && !project.is_archived;
  const [dialog, setDialog] = useState(null);
  const summary = useQuery({ queryKey: ['budgets', 'summary', project.id], queryFn: () => api.get(`budgets/summary?project_id=${project.id}`) });
  const entries = useQuery({ queryKey: ['budgets', 'entries', project.id], queryFn: () => api.get(`budgets?project_id=${project.id}`) });
  const close = () => setDialog(null);

  if (summary.isPending) return <Skeleton variant="rounded" height={420} />;
  if (summary.isError) return <ErrorState error={summary.error} onRetry={() => summary.refetch()} />;
  const s = summary.data;
  const over = s.remaining < 0;
  const stats = [
    { label: 'Planned', value: formatMoney(s.planned) },
    { label: 'Spent', value: formatMoney(s.spent), hint: `${s.used_pct}% of the plan` },
    { label: over ? 'Over budget by' : 'Remaining', value: formatMoney(Math.abs(s.remaining)), health: over ? 'off_track' : null },
    {
      label: 'Forecast at completion', value: s.forecast.projected_total ? formatMoney(s.forecast.projected_total) : 'Not yet',
      hint: forecastText(s.forecast), health: s.forecast.status === 'over' ? 'off_track' : null,
    },
  ];

  return (
    <Stack spacing={3}>
      {canManage && (
        <Box sx={{ display: 'flex', gap: 1.5, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
          <Button startIcon={<TuneRounded />} onClick={() => setDialog({ type: 'adjust' })}>Adjust budget</Button>
          <Button variant="contained" startIcon={<AddRounded />} onClick={() => setDialog({ type: 'spend' })}>Record spending</Button>
        </Box>
      )}

      <Card component="section" aria-label="Budget numbers"
        sx={{ display: 'grid', gridTemplateColumns: { xs: 'repeat(2, 1fr)', md: 'repeat(4, 1fr)' } }}>
        {stats.map((stat) => (
          <Box key={stat.label} sx={{ px: 3, py: 2.25, borderRight: 1, borderBottom: 1, borderColor: 'divider', mr: '-1px', mb: '-1px' }}>
            <Typography variant="body2" color="text.secondary">{stat.label}</Typography>
            <Typography sx={[{ fontSize: '1.5rem', fontWeight: 600, mt: 0.5 }, ...(stat.health ? healthText(stat.health) : [])]}>{stat.value}</Typography>
            {stat.hint && <Typography variant="body2" color="text.secondary">{stat.hint}</Typography>}
          </Box>
        ))}
      </Card>

      <Box sx={{ display: 'grid', gap: 3, gridTemplateColumns: { xs: '1fr', md: '3fr 2fr' }, alignItems: 'start' }}>
        <Section title="Spending over time" subtitle="Cumulative spending by month against the plan.">
          <BurnChart project={project} summary={s} />
        </Section>
        <Section title="By category">
          {s.by_category.length === 0 ? (
            <Typography color="text.secondary">No spending recorded yet.</Typography>
          ) : (
            <Stack spacing={2}>
              {s.by_category.map((c) => (
                <Box key={c.category}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                    <Typography sx={{ fontWeight: 500 }}>{capitalize(c.category)}</Typography>
                    <Typography sx={{ fontWeight: 600 }}>{formatMoney(c.amount)}</Typography>
                  </Box>
                  <LinearProgress variant="determinate" value={c.pct_of_spent} sx={{ height: 6, borderRadius: 3 }}
                    aria-label={`${capitalize(c.category)}: ${c.pct_of_spent}% of spending`} />
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                    {c.pct_of_spent}% of spending, {c.entries} {c.entries === 1 ? 'entry' : 'entries'}
                  </Typography>
                </Box>
              ))}
            </Stack>
          )}
        </Section>
      </Box>

      <Section title="Spending entries" subtitle="Every recorded expense. Changes and removals are kept in the audit log.">
        {entries.isPending ? <Skeleton variant="rounded" height={160} /> : entries.data.length === 0 ? (
          <EmptyState title="No spending yet" message="Record the first expense to start tracking the budget."
            action={canManage ? <Button variant="contained" onClick={() => setDialog({ type: 'spend' })}>Record spending</Button> : null} />
        ) : (
          <Box sx={{ overflowX: 'auto' }}>
            <Table size="small" aria-label="Spending entries">
              <TableHead>
                <TableRow>
                  <TableCell>Date</TableCell>
                  <TableCell>Category</TableCell>
                  <TableCell>What it was for</TableCell>
                  <TableCell>Recorded by</TableCell>
                  <TableCell align="right">Amount</TableCell>
                  {canManage && <TableCell align="right"><Box component="span" sx={{ position: 'absolute', left: -9999 }}>Actions</Box></TableCell>}
                </TableRow>
              </TableHead>
              <TableBody>
                {entries.data.map((entry) => (
                  <TableRow key={entry.id} hover>
                    <TableCell sx={{ whiteSpace: 'nowrap' }}>{formatDate(entry.entry_date)}</TableCell>
                    <TableCell><Chip size="small" label={capitalize(entry.category)} /></TableCell>
                    <TableCell>{entry.description || <Typography component="span" color="text.secondary">No description</Typography>}</TableCell>
                    <TableCell sx={{ whiteSpace: 'nowrap' }}>{entry.created_by_name}</TableCell>
                    <TableCell align="right" sx={{ fontWeight: 600, whiteSpace: 'nowrap' }}>{formatMoney(entry.amount)}</TableCell>
                    {canManage && (
                      <TableCell align="right" sx={{ whiteSpace: 'nowrap' }}>
                        <Tooltip title="Edit entry">
                          <IconButton size="small" aria-label={`Edit the ${formatMoney(entry.amount)} entry`} onClick={() => setDialog({ type: 'spend', entry })}>
                            <EditOutlined fontSize="small" />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title="Remove entry">
                          <IconButton size="small" aria-label={`Remove the ${formatMoney(entry.amount)} entry`} onClick={() => setDialog({ type: 'delete', entry })}>
                            <DeleteOutlineRounded fontSize="small" />
                          </IconButton>
                        </Tooltip>
                      </TableCell>
                    )}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Box>
        )}
      </Section>

      {dialog?.type === 'spend' && <SpendDialog project={project} entry={dialog.entry} onClose={close} />}
      {dialog?.type === 'adjust' && <AdjustBudgetDialog project={project} onClose={close} />}
      {dialog?.type === 'delete' && (
        <ApiDeleteDialog title={`Remove this ${formatMoney(dialog.entry.amount)} entry?`} confirmLabel="Remove"
          message="The totals update right away. The removed entry stays in the audit log, so nothing is lost."
          path={`budgets/${dialog.entry.id}`} success="Spending entry removed." onClose={close} />
      )}
    </Stack>
  );
}