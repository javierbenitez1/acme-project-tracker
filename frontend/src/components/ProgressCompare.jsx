import { Box, LinearProgress, Stack, Typography } from '@mui/material';
import { formatMoney } from '../utils/format';

function timeHint(project) {
  if (project.health === 'completed') return 'Finished';
  if (project.days_remaining < 0) return `${-project.days_remaining} days past the end date`;
  return `${project.days_remaining} days left`;
}

/** Work done next to time used and budget used, so a gap between them is easy to see. */
export default function ProgressCompare({ project, showBudget }) {
  const scheduleGap = project.time_elapsed_pct - project.progress;
  const budgetGap = project.budget_used_pct - project.progress;
  const rows = [
    { label: 'Work done', value: project.progress, color: 'primary', hint: `${project.milestones_done} of ${project.milestone_count} milestones done` },
    {
      label: 'Time used', value: project.time_elapsed_pct, hint: timeHint(project),
      color: scheduleGap >= 25 && project.health !== 'completed' ? 'warning' : 'secondary',
    },
    showBudget && {
      label: 'Budget used', value: project.budget_used_pct,
      hint: `${formatMoney(project.budget_spent)} of ${formatMoney(project.budget_planned)}`,
      color: project.budget_used_pct > 100 ? 'error' : budgetGap >= 25 ? 'warning' : 'secondary',
    },
  ].filter(Boolean);

  return (
    <Stack spacing={2.25}>
      {rows.map((row) => (
        <Box key={row.label}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', mb: 0.75 }}>
            <Typography sx={{ fontWeight: 600 }}>{row.label}</Typography>
            <Typography sx={{ fontWeight: 600 }}>{row.value}%</Typography>
          </Box>
          <LinearProgress variant="determinate" value={Math.min(row.value, 100)} color={row.color}
            sx={{ height: 8, borderRadius: 4 }} aria-label={`${row.label}: ${row.value}%`} />
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>{row.hint}</Typography>
        </Box>
      ))}
    </Stack>
  );
}