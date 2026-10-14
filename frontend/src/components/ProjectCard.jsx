import { Link as RouterLink } from 'react-router-dom';
import { Box, Card, CardActionArea, LinearProgress, Typography } from '@mui/material';
import HealthChip, { healthText } from './HealthChip';
import { formatDate } from '../utils/format';

function endText(project) {
  if (project.health === 'completed') return 'Completed';
  if (project.days_remaining < 0) return `Was due ${formatDate(project.end_date)}`;
  if (project.days_remaining === 0) return 'Ends today';
  return `Ends ${formatDate(project.end_date)}`;
}

export default function ProjectCard({ project, showBudget }) {
  const facts = [
    ['Milestones', `${project.milestones_done} of ${project.milestone_count}`],
    ['Team', project.member_count],
    showBudget ? ['Budget used', `${project.budget_used_pct}%`] : ['Time used', `${project.time_elapsed_pct}%`],
  ];
  return (
    <Card sx={{ height: '100%' }}>
      <CardActionArea component={RouterLink} to={`/projects/${project.id}`}
        sx={{ height: '100%', p: 2.5, display: 'flex', flexDirection: 'column', alignItems: 'stretch', justifyContent: 'flex-start', gap: 2 }}>
        <Box>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 1.5 }}>
            <Typography variant="h3" component="h2">{project.name}</Typography>
            <HealthChip value={project.health} size="small" />
          </Box>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
            {project.manager_name}{project.department ? `, ${project.department}` : ''}
          </Typography>
        </Box>
        <Box>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.75 }}>
            <Typography variant="body2" color="text.secondary">Work done</Typography>
            <Typography variant="body2" sx={{ fontWeight: 600 }}>{project.progress}%</Typography>
          </Box>
          <LinearProgress variant="determinate" value={project.progress} sx={{ height: 6, borderRadius: 3 }}
            aria-label={`${project.name}: ${project.progress}% of the work done`} />
        </Box>
        <Box component="dl" sx={{ m: 0, display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 1 }}>
          {facts.map(([label, value]) => (
            <Box key={label}>
              <Typography component="dt" variant="body2" color="text.secondary">{label}</Typography>
              <Typography component="dd" sx={{ m: 0, fontWeight: 600 }}>{value}</Typography>
            </Box>
          ))}
        </Box>
        <Box sx={{ mt: 'auto', display: 'flex', justifyContent: 'space-between', gap: 2, alignItems: 'baseline', minWidth: 0 }}>
          <Typography variant="body2" color="text.secondary" sx={{ flexShrink: 0 }}>{endText(project)}</Typography>
          {project.risk_reasons[0] && (
            <Typography variant="body2" noWrap title={project.risk_reasons[0]} sx={[{ fontWeight: 500, minWidth: 0 }, ...healthText(project.health)]}>
              {project.risk_reasons[0]}
            </Typography>
          )}
        </Box>
      </CardActionArea>
    </Card>
  );
}