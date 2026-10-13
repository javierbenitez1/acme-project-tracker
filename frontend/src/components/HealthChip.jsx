import { Box } from '@mui/material';
import { health } from '../theme';

/** Darker text in light mode and lighter text in dark mode keep every health label readable (WCAG AA). */
export const HEALTH_TEXT = {
  on_track: ['#1F6B45', '#7DD3A6'],
  at_risk: ['#875A00', '#F0C266'],
  off_track: ['#A3321F', '#F29A8A'],
  completed: ['#46556C', '#B4C0D3'],
  archived: ['#5D6778', '#AEB7C6'],
};

export const healthText = (value) => {
  const [light, dark] = HEALTH_TEXT[value] || HEALTH_TEXT.archived;
  return [{ color: light }, (theme) => theme.applyStyles('dark', { color: dark })];
};

export default function HealthChip({ value, size = 'medium' }) {
  const info = health[value] || { label: value, color: '#8A94A6' };
  return (
    <Box
      component="span"
      sx={[
        {
          display: 'inline-flex', alignItems: 'center', gap: 0.75, px: 1, py: 0.25, borderRadius: '6px',
          fontSize: size === 'small' ? '0.75rem' : '0.8125rem', fontWeight: 600, whiteSpace: 'nowrap',
          bgcolor: `${info.color}1F`,
        },
        ...healthText(value),
      ]}
    >
      <Box component="span" aria-hidden="true" sx={{ width: 7, height: 7, borderRadius: '50%', bgcolor: info.color }} />
      {info.label}
    </Box>
  );
}