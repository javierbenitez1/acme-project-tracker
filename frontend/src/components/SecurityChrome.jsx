import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Box, Button, Chip, Dialog, DialogActions, DialogContent, DialogTitle, LinearProgress, Stack, Typography,
} from '@mui/material';
import LockOutlined from '@mui/icons-material/LockOutlined';
import { useAuth } from '../auth/AuthContext';
import { api } from '../services/api';
import { useToast } from './Toast';
import Section from './Section';
import {
  ACTIVITY_KEY, IDLE_LIMIT_MS, WARNING_MS, countdown, idleState, signInNotice, signInTime,
} from '../utils/session';

const ACTIVITY_EVENTS = ['mousemove', 'mousedown', 'keydown', 'scroll', 'touchstart', 'wheel'];

/** The data classification label every page of an internal bank tool carries. */
export function ClassificationBanner() {
  return (
    <Box role="note" sx={{
      display: 'flex', alignItems: 'center', gap: 1, mb: 2.5, px: 1.5, py: 0.75, borderRadius: '8px',
      border: 1, borderColor: 'divider', bgcolor: 'action.hover', color: 'text.secondary', fontSize: '0.8125rem',
    }}>
      <LockOutlined sx={{ fontSize: 16 }} />
      <Box component="span" sx={{ fontWeight: 700, letterSpacing: '0.04em', color: 'text.primary' }}>INTERNAL USE ONLY</Box>
      <Box component="span" sx={{ display: { xs: 'none', sm: 'inline' } }}>
        ACME confidential. Don't share outside the company. Activity is logged.
      </Box>
    </Box>
  );
}

/** Signs people out after 15 minutes without activity, with a 2-minute warning, and shows a notice after
 * sign-in: their last sign-in, or a security warning if someone tried and failed to sign in as them. */
export function SessionGuard() {
  const { user, logout } = useAuth();
  const toast = useToast();
  const last = useRef(Date.now());
  const phase = useRef('active');
  const [state, setState] = useState({ phase: 'active', secondsLeft: IDLE_LIMIT_MS / 1000 });

  const remember = (time) => {
    last.current = time;
    try { localStorage.setItem(ACTIVITY_KEY, String(time)); } catch { /* storage can be unavailable */ }
  };

  useEffect(() => {
    remember(Date.now());
    const onActivity = () => {
      // During the warning only the "Stay signed in" button counts, so a stray mouse move can't hide it
      if (phase.current === 'active' && Date.now() - last.current > 1000) remember(Date.now());
    };
    ACTIVITY_EVENTS.forEach((name) => window.addEventListener(name, onActivity, { passive: true }));
    const timer = setInterval(() => {
      let shared = 0;
      try { shared = Number(localStorage.getItem(ACTIVITY_KEY)) || 0; } catch { /* ignore */ }
      const next = idleState(Math.max(last.current, shared), Date.now());
      phase.current = next.phase;
      setState((prev) => (prev.phase === next.phase && prev.secondsLeft === next.secondsLeft ? prev : next));
    }, 1000);
    return () => {
      ACTIVITY_EVENTS.forEach((name) => window.removeEventListener(name, onActivity));
      clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    if (state.phase !== 'expired') return;
    logout();
    toast.info('You were signed out after 15 minutes without activity, to keep ACME data safe.');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.phase]);

  const signIns = useQuery({ queryKey: ['auth', 'sign-ins'], queryFn: () => api.get('auth/sign-ins'), staleTime: Infinity });
  useEffect(() => {
    const summary = signIns.data;
    if (!summary?.current) return;
    const key = `throughline:notice:${user.id}`;
    try {
      if (sessionStorage.getItem(key) === String(summary.current.id)) return;
      sessionStorage.setItem(key, String(summary.current.id));
    } catch { /* ignore */ }
    const notice = signInNotice(summary, user.name.split(' ')[0]);
    if (notice) toast[notice.severity](notice.text);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [signIns.data]);

  const stay = () => {
    remember(Date.now());
    phase.current = 'active';
    setState({ phase: 'active', secondsLeft: IDLE_LIMIT_MS / 1000 });
  };

  return (
    <Dialog open={state.phase === 'warning'} maxWidth="xs" fullWidth aria-labelledby="idle-title" onClose={stay}>
      <DialogTitle id="idle-title">Are you still there?</DialogTitle>
      <DialogContent>
        <Typography color="text.secondary">
          For security, you'll be signed out in <b>{countdown(state.secondsLeft)}</b> because there hasn't been any activity.
        </Typography>
        <LinearProgress variant="determinate" value={(100 * state.secondsLeft) / (WARNING_MS / 1000)} sx={{ mt: 2, borderRadius: 1 }} />
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2.5 }}>
        <Button color="inherit" onClick={() => logout()}>Sign out now</Button>
        <Button variant="contained" onClick={stay} autoFocus>Stay signed in</Button>
      </DialogActions>
    </Dialog>
  );
}

/** Recent sign-in attempts on the profile page, so people can spot anything that wasn't them. */
export function RecentSignIns() {
  const query = useQuery({ queryKey: ['auth', 'sign-ins'], queryFn: () => api.get('auth/sign-ins') });
  const events = query.data?.recent || [];
  return (
    <Section title="Recent sign-ins" subtitle="If you don't recognise one, change your password right away.">
      {query.isPending && <LinearProgress aria-label="Loading sign-ins" />}
      {!query.isPending && events.length === 0 && <Typography color="text.secondary">No sign-ins recorded yet.</Typography>}
      <Stack divider={<Box sx={{ borderTop: 1, borderColor: 'divider' }} />}>
        {events.map((event, i) => (
          <Box key={event.id} sx={{ display: 'flex', alignItems: 'center', gap: 2, py: 1.25 }}>
            <Box sx={{ flex: 1, minWidth: 0 }}>
              <Typography sx={{ fontWeight: 500 }}>
                {signInTime(event.created_at)}{i === 0 && event.succeeded ? ' (this session)' : ''}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {event.device || 'Unknown device'}{event.ip_masked ? `, network ${event.ip_masked}` : ''}
              </Typography>
            </Box>
            <Chip size="small" variant="outlined" color={event.succeeded ? 'success' : 'error'}
              label={event.succeeded ? 'Signed in' : event.blocked ? 'Refused (account locked)' : 'Failed attempt'} />
          </Box>
        ))}
      </Stack>
    </Section>
  );
}