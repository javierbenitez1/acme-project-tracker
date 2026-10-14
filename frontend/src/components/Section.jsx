import { Box, Card, CardContent, Typography } from '@mui/material';

/** A titled card used for every content block in the app, so spacing and headings stay consistent. */
export default function Section({ title, subtitle, action, children }) {
  return (
    <Card component="section" aria-label={title} sx={{ height: '100%' }}>
      <CardContent sx={{ p: { xs: 2, md: 3 }, '&:last-child': { pb: { xs: 2, md: 3 } } }}>
        <Box sx={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 2, mb: subtitle ? 0.5 : 2 }}>
          <Typography variant="h3" component="h2">{title}</Typography>
          {action}
        </Box>
        {subtitle && <Typography variant="body2" color="text.secondary" sx={{ mb: 2.5 }}>{subtitle}</Typography>}
        {children}
      </CardContent>
    </Card>
  );
}