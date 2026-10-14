import { useMediaQuery } from 'react-responsive';
import {
  Alert, Button, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle, Stack,
} from '@mui/material';

/** The shell every form uses: title, error banner, fields, and Cancel / submit buttons. Full screen on phones. */
export default function FormDialog({ title, submitLabel, busy, error, onSubmit, onClose, children, maxWidth = 'sm' }) {
  const fullScreen = useMediaQuery({ maxWidth: 599 });
  return (
    <Dialog open onClose={busy ? undefined : onClose} fullScreen={fullScreen} maxWidth={maxWidth} fullWidth aria-labelledby="form-dialog-title">
      <form noValidate onSubmit={(event) => { event.preventDefault(); onSubmit(); }}>
        <DialogTitle id="form-dialog-title">{title}</DialogTitle>
        <DialogContent>
          <Stack spacing={2.5} sx={{ pt: 1 }}>
            {error && <Alert severity="error">{error}</Alert>}
            {children}
          </Stack>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2.5 }}>
          <Button onClick={onClose} disabled={busy} color="inherit">Cancel</Button>
          <Button type="submit" variant="contained" disabled={busy}>
            {busy ? <CircularProgress size={20} color="inherit" aria-label="Saving" /> : submitLabel}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}