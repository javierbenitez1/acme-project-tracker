import {
  Button, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle, Typography,
} from '@mui/material';
import useApiMutation from '../hooks/useApiMutation';
import { api } from '../services/api';

export default function ConfirmDialog({ title, message, confirmLabel, busy, destructive, onConfirm, onClose }) {
  return (
    <Dialog open onClose={busy ? undefined : onClose} maxWidth="xs" fullWidth aria-labelledby="confirm-title">
      <DialogTitle id="confirm-title">{title}</DialogTitle>
      <DialogContent><Typography color="text.secondary">{message}</Typography></DialogContent>
      <DialogActions sx={{ px: 3, pb: 2.5 }}>
        <Button onClick={onClose} disabled={busy} color="inherit">Cancel</Button>
        <Button onClick={onConfirm} variant="contained" color={destructive ? 'error' : 'primary'} disabled={busy}>
          {busy ? <CircularProgress size={20} color="inherit" aria-label="Working" /> : confirmLabel}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

/** A confirm dialog that sends a DELETE to the given API path. */
export function ApiDeleteDialog({ title, message, path, success, confirmLabel = 'Delete', onClose }) {
  const remove = useApiMutation(() => api.delete(path), { success, onSuccess: onClose });
  return (
    <ConfirmDialog title={title} message={message} confirmLabel={confirmLabel} destructive
      busy={remove.isPending} onConfirm={() => remove.mutate()} onClose={onClose} />
  );
}