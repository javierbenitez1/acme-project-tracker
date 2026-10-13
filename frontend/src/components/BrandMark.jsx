import { Box, Typography } from '@mui/material';

/** The Throughline mark: a route line from a start station to a goal station. */
export default function BrandMark({ color = 'text.primary', size = 28 }) {
  return (
    <Box sx={{ display: 'inline-flex', alignItems: 'center', gap: 1.25, color }}>
      <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true" focusable="false">
        <path d="M4 22h8l8-12h8" fill="none" stroke="#4FB3B1" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="4" cy="22" r="3.5" fill="currentColor" />
        <circle cx="28" cy="10" r="3.5" fill="#E0A935" />
      </svg>
      <Typography component="span" sx={{ fontWeight: 700, fontSize: '1.125rem', letterSpacing: '-0.01em', color: 'inherit' }}>
        Throughline
      </Typography>
    </Box>
  );
}