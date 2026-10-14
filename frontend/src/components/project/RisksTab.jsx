import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Alert, Box, Button, Chip, IconButton, MenuItem, Skeleton, Stack, TextField, Tooltip, Typography,
} from '@mui/material';
import AddRounded from '@mui/icons-material/AddRounded';
import EditOutlined from '@mui/icons-material/EditOutlined';
import Section from '../Section';
import FormDialog from '../FormDialog';
import { ErrorState } from '../PageState';
import useApiMutation from '../../hooks/useApiMutation';
import useFormState from '../../hooks/useFormState';
import { api } from '../../services/api';
import { formatDate } from '../../utils/format';
import {
  ACTIVE_STATUSES, CATEGORIES, IMPACT, LEVELS, LIKELIHOOD, STATUS_LABELS, categoryLabel, matrixCells,
  registerSummary, riskLevel,
} from '../../utils/risks';

function LevelChip({ level, score }) {
  const { label, color } = LEVELS[level];
  return (
    <Chip size="small" label={`${label} ${score}`}
      sx={{ fontWeight: 700, bgcolor: `${color}26`, border: `1px solid ${color}`, color: 'text.primary' }} />
  );
}

function RiskMatrix({ risks }) {
  const rows = matrixCells(risks);
  return (
    <Box>
      <Typography sx={{ fontWeight: 600, mb: 0.5 }}>Risk matrix</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
        Impact runs up, likelihood runs right. Hover a cell to see its risks.
      </Typography>
      <Box role="img" aria-label={`Risk matrix with ${risks.length} active risks`}
        sx={{ display: 'grid', gridTemplateColumns: 'auto repeat(5, minmax(34px, 1fr))', gap: 0.5, alignItems: 'center' }}>
        {rows.map((row) => [
          <Typography key={`label-${row[0].impact}`} variant="body2" color="text.secondary" sx={{ pr: 1, fontSize: '0.75rem' }}>
            {IMPACT[row[0].impact - 1]}
          </Typography>,
          ...row.map((cell) => {
            const { color } = LEVELS[cell.level];
            const titles = cell.risks.map((r) => r.title);
            return (
              <Tooltip key={`${cell.impact}-${cell.likelihood}`} arrow disableHoverListener={!titles.length}
                title={titles.join(', ')}>
                <Box sx={{
                  height: 40, borderRadius: '6px', display: 'flex', alignItems: 'center', justifyContent: 'center',
                  bgcolor: `${color}${titles.length ? '66' : '1F'}`, fontWeight: 700,
                  outline: titles.length ? `2px solid ${color}` : 'none',
                }}>
                  {titles.length || ''}
                </Box>
              </Tooltip>
            );
          }),
        ])}
        <Box />
        {LIKELIHOOD.map((label) => (
          <Typography key={label} variant="body2" color="text.secondary"
            sx={{ fontSize: '0.7rem', textAlign: 'center', lineHeight: 1.2, pt: 0.5 }}>
            {label}
          </Typography>
        ))}
      </Box>
    </Box>
  );
}

function RiskRow({ risk, canManage, onEdit }) {
  const { color } = LEVELS[risk.level];
  const facts = [
    categoryLabel(risk.category),
    risk.owner_name ? `Owner: ${risk.owner_name}` : 'No owner yet',
    risk.review_date && `Review ${formatDate(risk.review_date)}`,
  ].filter(Boolean);
  return (
    <Box sx={{ border: 1, borderColor: 'divider', borderLeft: `4px solid ${color}`, borderRadius: '8px', p: 2 }}>
      <Box sx={{ display: 'flex', gap: 1.5, alignItems: 'flex-start', justifyContent: 'space-between' }}>
        <Box sx={{ minWidth: 0 }}>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, alignItems: 'center', mb: 0.5 }}>
            <Typography sx={{ fontWeight: 600 }}>{risk.title}</Typography>
            <LevelChip level={risk.level} score={risk.score} />
            <Chip size="small" variant="outlined" label={STATUS_LABELS[risk.status]} />
          </Box>
          <Typography variant="body2" color="text.secondary">
            {facts.join(' · ')}
            {risk.review_overdue && (
              <Typography component="span" variant="body2" sx={{ color: 'error.main', fontWeight: 600 }}> (review overdue)</Typography>
            )}
          </Typography>
          {risk.description && <Typography variant="body2" sx={{ mt: 1 }}>{risk.description}</Typography>}
          {risk.mitigation && <Typography variant="body2" sx={{ mt: 1 }}><b>Plan:</b> {risk.mitigation}</Typography>}
        </Box>
        {canManage && (
          <Tooltip title="Edit risk">
            <IconButton aria-label={`Edit ${risk.title}`} onClick={() => onEdit(risk)}><EditOutlined /></IconButton>
          </Tooltip>
        )}
      </Box>
    </Box>
  );
}

function RiskDialog({ project, risk, suggestion, onClose }) {
  const editing = Boolean(risk);
  const source = risk || suggestion || {};
  const form = useFormState({
    title: source.title || '',
    description: source.description || '',
    category: source.category || 'schedule',
    likelihood: String(source.likelihood || 3),
    impact: String(source.impact || 3),
    owner_id: source.owner_id ? String(source.owner_id) : '',
    mitigation: source.mitigation || '',
    review_date: source.review_date || '',
    status: risk?.status || 'open',
  });
  const save = useApiMutation(
    (body) => (editing ? api.put(`projects/${project.id}/risks/${risk.id}`, body) : api.post(`projects/${project.id}/risks`, body)),
    { success: editing ? 'Risk updated.' : 'Risk added to the register.', onSuccess: onClose, onError: (error) => form.fail(error) },
  );
  const v = form.values;
  const score = Number(v.likelihood) * Number(v.impact);
  const level = riskLevel(score);

  function submit() {
    if (!form.check({ title: !v.title.trim() && 'Give the risk a short title.' })) return;
    const body = {
      title: v.title.trim(),
      description: v.description.trim() || null,
      category: v.category,
      likelihood: Number(v.likelihood),
      impact: Number(v.impact),
      owner_id: v.owner_id ? Number(v.owner_id) : null,
      mitigation: v.mitigation.trim() || null,
      review_date: v.review_date || null,
    };
    if (editing) body.status = v.status;
    else if (suggestion) body.source_key = suggestion.source_key;
    save.mutate(body);
  }

  return (
    <FormDialog title={editing ? 'Edit risk' : suggestion ? 'Add the suggested risk' : 'Add a risk'}
      submitLabel={editing ? 'Save changes' : 'Add risk'} busy={save.isPending} error={form.formError}
      onSubmit={submit} onClose={onClose}>
      <TextField label="Risk" required autoFocus {...form.field('title', 'What might go wrong, in a few words.')} />
      <TextField label="Details" multiline minRows={2} {...form.field('description')} />
      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
        <TextField select fullWidth label="Likelihood" {...form.field('likelihood')}>
          {LIKELIHOOD.map((label, i) => <MenuItem key={label} value={String(i + 1)}>{i + 1}. {label}</MenuItem>)}
        </TextField>
        <TextField select fullWidth label="Impact" {...form.field('impact')}>
          {IMPACT.map((label, i) => <MenuItem key={label} value={String(i + 1)}>{i + 1}. {label}</MenuItem>)}
        </TextField>
      </Stack>
      <Alert icon={false} severity={level === 'high' ? 'error' : level === 'medium' ? 'warning' : 'success'}>
        Score {score} of 25: a {LEVELS[level].label.toLowerCase()} risk.
      </Alert>
      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
        <TextField select fullWidth label="Category" {...form.field('category')}>
          {CATEGORIES.map(([value, label]) => <MenuItem key={value} value={value}>{label}</MenuItem>)}
        </TextField>
        <TextField select fullWidth label="Owner" {...form.field('owner_id', 'Someone on the project team.')}>
          <MenuItem value="">No owner yet</MenuItem>
          {project.members.map((m) => <MenuItem key={m.id} value={String(m.id)}>{m.name}</MenuItem>)}
        </TextField>
      </Stack>
      <TextField label="Mitigation plan" multiline minRows={2}
        {...form.field('mitigation', 'What you will do to make it less likely, or less damaging if it happens.')} />
      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
        <TextField type="date" fullWidth label="Review by" slotProps={{ inputLabel: { shrink: true } }}
          {...form.field('review_date', 'You get an Action Center reminder if this date passes.')} />
        {editing && (
          <TextField select fullWidth label="Status" {...form.field('status')}>
            {Object.entries(STATUS_LABELS).map(([value, label]) => <MenuItem key={value} value={value}>{label}</MenuItem>)}
          </TextField>
        )}
      </Stack>
    </FormDialog>
  );
}

function Suggestions({ items, onAccept, onDismiss, busy }) {
  return (
    <Section title="Suggested risks"
      subtitle="Spotted in this project's live data: the critical path, the delivery forecast and the budget forecast. Add the ones that matter.">
      <Stack spacing={1.5}>
        {items.map((s) => (
          <Box key={s.source_key} sx={{ border: 1, borderColor: 'divider', borderRadius: '8px', p: 2 }}>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, alignItems: 'center', mb: 0.5 }}>
              <Typography sx={{ fontWeight: 600 }}>{s.title}</Typography>
              <LevelChip level={s.level} score={s.score} />
            </Box>
            <Typography variant="body2" color="text.secondary">{s.description}</Typography>
            <Box sx={{ display: 'flex', gap: 1, mt: 1.5 }}>
              <Button size="small" variant="contained" onClick={() => onAccept(s)}>Add to register</Button>
              <Button size="small" color="inherit" disabled={busy} onClick={() => onDismiss(s.source_key)}>Not relevant</Button>
            </Box>
          </Box>
        ))}
      </Stack>
    </Section>
  );
}

/** Risk register for one project: suggestions from live signals, the register itself, and a 5x5 matrix. */
export default function RisksTab({ project }) {
  const query = useQuery({
    queryKey: ['project', String(project.id), 'risks'],
    queryFn: () => api.get(`projects/${project.id}/risks`),
    refetchInterval: 30_000,
  });
  const [dialog, setDialog] = useState(null);
  const [showClosed, setShowClosed] = useState(false);
  const dismiss = useApiMutation(
    (sourceKey) => api.post(`projects/${project.id}/risks/dismiss`, { source_key: sourceKey }),
    { success: "Dismissed. It won't be suggested again." },
  );

  if (query.isPending) return <Skeleton variant="rounded" height={320} />;
  if (query.isError) return <ErrorState error={query.error} onRetry={() => query.refetch()} />;

  const { risks, suggestions, summary, can_manage: canManage } = query.data;
  const active = risks.filter((r) => ACTIVE_STATUSES.includes(r.status));
  const closed = risks.filter((r) => !ACTIVE_STATUSES.includes(r.status));

  return (
    <Stack spacing={3}>
      {canManage && suggestions.length > 0 && (
        <Suggestions items={suggestions} busy={dismiss.isPending}
          onAccept={(suggestion) => setDialog({ suggestion })} onDismiss={(key) => dismiss.mutate(key)} />
      )}
      <Section title="Risk register"
        subtitle="Things that might go wrong, scored by likelihood and impact, each with an owner and a plan."
        action={canManage ? <Button startIcon={<AddRounded />} onClick={() => setDialog({})}>Add risk</Button> : null}>
        <Typography sx={{ mb: 2.5, fontWeight: 500 }}>{registerSummary(summary)}</Typography>
        <Box sx={{ display: 'grid', gap: 3, gridTemplateColumns: { xs: '1fr', md: 'minmax(0, 1fr) minmax(260px, 340px)' }, alignItems: 'start' }}>
          <Stack spacing={1.5}>
            {active.length === 0 && (
              <Typography color="text.secondary">
                {canManage ? 'Nothing logged yet. Add a risk, or start from a suggestion above.' : 'Nothing logged yet.'}
              </Typography>
            )}
            {active.map((risk) => <RiskRow key={risk.id} risk={risk} canManage={canManage} onEdit={(r) => setDialog({ risk: r })} />)}
            {closed.length > 0 && (
              <Box>
                <Button size="small" color="inherit" onClick={() => setShowClosed(!showClosed)}>
                  {showClosed ? 'Hide' : 'Show'} closed risks ({closed.length})
                </Button>
              </Box>
            )}
            {showClosed && closed.map((risk) => <RiskRow key={risk.id} risk={risk} canManage={canManage} onEdit={(r) => setDialog({ risk: r })} />)}
          </Stack>
          <RiskMatrix risks={active} />
        </Box>
      </Section>
      {dialog && <RiskDialog project={project} risk={dialog.risk} suggestion={dialog.suggestion} onClose={() => setDialog(null)} />}
    </Stack>
  );
}