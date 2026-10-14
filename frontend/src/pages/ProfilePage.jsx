import { Box, Stack, TextField, Typography } from '@mui/material';
import { Button, CircularProgress } from '@mui/material';
import { useAuth } from '../auth/AuthContext';
import { api } from '../services/api';
import useFormState from '../hooks/useFormState';
import useApiMutation from '../hooks/useApiMutation';
import Section from '../components/Section';
import { useToast } from '../components/Toast';
import { ROLE_LABELS } from '../navigation';

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$/;

export default function ProfilePage() {
  const { user, updateUser, logout } = useAuth();
  const toast = useToast();
  const details = useFormState({ name: user.name, email: user.email });
  const password = useFormState({ current_password: '', new_password: '', confirm: '' });

  const saveDetails = useApiMutation((body) => api.put(`users/${user.id}`, body), {
    success: 'Your details are saved.', onSuccess: (data) => updateUser({ name: data.name, email: data.email }), onError: details.fail,
  });
  const changePassword = useApiMutation((body) => api.post('auth/password', body), {
    onSuccess: () => { toast.success('Password changed. Sign in again with your new password.'); logout(); },
    onError: password.fail,
  });

  function submitDetails(event) {
    event.preventDefault();
    const v = details.values;
    const ok = details.check({ name: !v.name.trim() && 'Enter your name.', email: !EMAIL_RE.test(v.email.trim()) && 'Enter a valid email address.' });
    if (!ok) return;
    const body = {};
    if (v.name.trim() !== user.name) body.name = v.name.trim();
    if (v.email.trim().toLowerCase() !== user.email) body.email = v.email.trim();
    if (!Object.keys(body).length) {
      details.setFormError('Nothing has changed.');
      return;
    }
    saveDetails.mutate(body);
  }

  function submitPassword(event) {
    event.preventDefault();
    const v = password.values;
    const ok = password.check({
      current_password: !v.current_password && 'Enter your current password.',
      new_password: (v.new_password.length < 8 || !/[A-Za-z]/.test(v.new_password) || !/\d/.test(v.new_password)) && 'Use at least 8 characters with a letter and a number.',
      confirm: v.confirm !== v.new_password && "The passwords don't match.",
    });
    if (ok) changePassword.mutate({ current_password: v.current_password, new_password: v.new_password });
  }

  return (
    <Stack spacing={3} sx={{ maxWidth: 720 }}>
      <Box>
        <Typography variant="h1">Your profile</Typography>
        <Typography color="text.secondary" sx={{ mt: 1 }}>
          Signed in as {user.username}, {ROLE_LABELS[user.role]}{user.job_title ? `, ${user.job_title}` : ''}.
        </Typography>
      </Box>
      <Section title="Your details" subtitle="Your name and email show up on projects, action items and the audit log.">
        <Box component="form" noValidate onSubmit={submitDetails}>
          <Stack spacing={2.5}>
            {details.formError && <Typography sx={{ color: 'error.main' }}>{details.formError}</Typography>}
            <TextField label="Full name" required {...details.field('name')} />
            <TextField label="Email" type="email" required {...details.field('email')} />
            <Box><Button type="submit" variant="contained" disabled={saveDetails.isPending}>{saveDetails.isPending ? <CircularProgress size={20} color="inherit" aria-label="Saving" /> : 'Save details'}</Button></Box>
          </Stack>
        </Box>
      </Section>
      <Section title="Change your password" subtitle="Changing it signs you out on every device.">
        <Box component="form" noValidate onSubmit={submitPassword}>
          <Stack spacing={2.5}>
            {password.formError && <Typography sx={{ color: 'error.main' }}>{password.formError}</Typography>}
            <TextField label="Current password" type="password" required autoComplete="current-password" {...password.field('current_password')} />
            <TextField label="New password" type="password" required autoComplete="new-password" {...password.field('new_password', 'At least 8 characters, with a letter and a number.')} />
            <TextField label="Confirm new password" type="password" required autoComplete="new-password" {...password.field('confirm')} />
            <Box><Button type="submit" variant="contained" disabled={changePassword.isPending}>{changePassword.isPending ? <CircularProgress size={20} color="inherit" aria-label="Saving" /> : 'Change password'}</Button></Box>
          </Stack>
        </Box>
      </Section>
    </Stack>
  );
}