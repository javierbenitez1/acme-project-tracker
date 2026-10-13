import { Alert, Box, Button, Typography } from '@mui/material';

export function ErrorState({ error, onRetry, title = "This page couldn't load" }) {
  return (
    <Alert
      severity="error"
      action={onRetry ? <Button color="inherit" size="small" onClick={onRetry}>Try again</Button> : null}
    >
      <strong>{title}.</strong> {error?.message || 'Something went wrong. Try again in a moment.'}
    </Alert>
  );
}

export function EmptyState({ title, message, action }) {
  return (
    <Box sx={{ textAlign: 'center', py: 6, px: 2 }}>
      <Typography variant="h3" component="p" gutterBottom>{title}</Typography>
      {message && <Typography color="text.secondary" sx={{ maxWidth: 440, mx: 'auto', mb: action ? 3 : 0 }}>{message}</Typography>}
      {action}
    </Box>
  );
}