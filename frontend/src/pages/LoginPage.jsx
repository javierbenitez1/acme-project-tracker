import { useEffect, useState } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { useMediaQuery } from 'react-responsive';
import {
  Alert, Box, Button, CircularProgress, Divider, IconButton, InputAdornment, Stack, TextField, Typography,
} from '@mui/material';
import KeyboardCapslockRounded from '@mui/icons-material/KeyboardCapslockRounded';
import LockOutlined from '@mui/icons-material/LockOutlined';
import VisibilityOutlined from '@mui/icons-material/VisibilityOutlined';
import VisibilityOffOutlined from '@mui/icons-material/VisibilityOffOutlined';
import { useAuth } from '../auth/AuthContext';
import BrandMark from '../components/BrandMark';
import { api } from '../services/api';
import { ink } from '../theme';

/** Demo accounts come from scripts/seed_demo.py. Set VITE_DEMO_LOGINS=false to hide them. */
const DEMO_ACCOUNTS = [
  { role: 'Administrator', name: 'Javier Benitez', blurb: 'sets up projects and people', username: 'admin', password: 'Admin123!' },
  { role: 'Manager', name: 'Dana Whitfield', blurb: 'runs the mobile banking project', username: 'dana.whitfield', password: 'Demo1234!' },
  { role: 'Employee', name: 'Leo Martins', blurb: 'builds the transfers module', username: 'leo.martins', password: 'Demo1234!' },
];
const SHOW_DEMO = import.meta.env.VITE_DEMO_LOGINS !== 'false';

const STATIONS = [
  { x: 40, label: 'Discovery', state: 'done' },
  { x: 150, label: 'Design', state: 'done' },
  { x: 260, label: 'Build', state: 'current' },
  { x: 370, label: 'Launch', state: 'next' },
];
const STATION_STROKE = { done: '#4FB3B1', current: '#E0A935', next: '#3A4A63' };
const DRAW_SECONDS = 1.2;

/** The brand mark brought to life: the line draws itself, each station lights up as the line reaches it,
 * and a glowing "train" keeps travelling to today's station. Everything holds still for reduced motion. */
function RouteIllustration() {
  const stationDelay = (x) => ((x - 40) / 220) * DRAW_SECONDS;
  return (
    <Box component="svg" viewBox="0 0 410 120" role="img" aria-label="A project moving through four milestones, currently in Build"
      sx={{
        width: '100%', maxWidth: 440, display: 'block', overflow: 'visible',
        '& .route-done': { strokeDasharray: 220, strokeDashoffset: 220, animation: `route-draw ${DRAW_SECONDS}s ease-out forwards` },
        '& .route-next': { opacity: 0, animation: `route-fade 0.6s ease-out ${DRAW_SECONDS}s forwards` },
        '& .station': { transformBox: 'fill-box', transformOrigin: 'center', opacity: 0, animation: 'station-in 0.45s cubic-bezier(.2,1.4,.4,1) forwards' },
        '& .station-label': { opacity: 0, animation: 'route-fade 0.5s ease-out forwards' },
        '& .station-pulse': { transformBox: 'fill-box', transformOrigin: 'center', opacity: 0,
          animation: `station-pulse 2.4s ease-out ${DRAW_SECONDS + 0.4}s infinite` },
        '& .train': { opacity: 0, animation: `train-run 4.5s ease-in-out ${DRAW_SECONDS + 0.6}s infinite` },
        '@keyframes route-draw': { to: { strokeDashoffset: 0 } },
        '@keyframes route-fade': { to: { opacity: 1 } },
        '@keyframes station-in': { from: { opacity: 0, transform: 'scale(0.3)' }, to: { opacity: 1, transform: 'scale(1)' } },
        '@keyframes station-pulse': { '0%': { opacity: 0.9, transform: 'scale(1)' }, '100%': { opacity: 0, transform: 'scale(2.1)' } },
        '@keyframes train-run': {
          '0%': { opacity: 0, transform: 'translateX(0)' },
          '12%': { opacity: 1 },
          '78%': { opacity: 1, transform: 'translateX(220px)' },
          '100%': { opacity: 0, transform: 'translateX(220px)' },
        },
        '@media (prefers-reduced-motion: reduce)': {
          '& .route-done, & .route-next, & .station, & .station-label': { animation: 'none', opacity: 1, strokeDashoffset: 0 },
          '& .station-pulse, & .train': { animation: 'none', display: 'none' },
        },
      }}>
      <defs>
        <radialGradient id="train-glow">
          <stop offset="0%" stopColor="#FFFFFF" />
          <stop offset="45%" stopColor="#8FE3E0" />
          <stop offset="100%" stopColor="#4FB3B1" stopOpacity="0" />
        </radialGradient>
      </defs>
      <line className="route-done" x1="40" y1="56" x2="260" y2="56" stroke="#4FB3B1" strokeWidth="6" strokeLinecap="round" />
      <line className="route-next" x1="260" y1="56" x2="370" y2="56" stroke="#3A4A63" strokeWidth="6" strokeLinecap="round" strokeDasharray="1 12" />
      <circle className="station-pulse" cx="260" cy="56" r="13" fill="none" stroke="#E0A935" strokeWidth="3" />
      <circle className="train" cx="40" cy="56" r="9" fill="url(#train-glow)" />
      {STATIONS.map((station) => {
        const delay = station.state === 'next' ? DRAW_SECONDS + 0.3 : stationDelay(station.x);
        return (
          <g key={station.label}>
            <circle className="station" style={{ animationDelay: `${delay}s` }} cx={station.x} cy="56"
              r={station.state === 'current' ? 13 : 10} fill={ink} stroke={STATION_STROKE[station.state]} strokeWidth="5" />
            <text className="station-label" style={{ animationDelay: `${delay + 0.1}s` }} x={station.x} y="100" textAnchor="middle"
              fill={station.state === 'next' ? '#7F8DA3' : '#C9D3E1'} fontSize="13">
              {station.label}
            </text>
          </g>
        );
      })}
      <text className="station-label" style={{ animationDelay: `${DRAW_SECONDS}s` }} x="260" y="24" textAnchor="middle"
        fill="#E0A935" fontSize="12" fontWeight="600">Today</text>
    </Box>
  );
}

const STATUS = {
  checking: { color: '#8E9BB0', text: 'Checking systems...' },
  waking: { color: '#E0A935', text: 'Waking up the database. This can take up to 30 seconds.' },
  ok: { color: '#2F8F5B', text: 'All systems operational' },
  down: { color: '#C2412D', text: "Can't reach the server right now. Try again in a minute." },
};

/** Pings the API when the page opens. It reports the status, and it wakes the serverless database early,
 * so signing in is fast. */
function SystemStatus() {
  const [state, setState] = useState('checking');
  useEffect(() => {
    let done = false;
    const slow = setTimeout(() => { if (!done) setState('waking'); }, 2500);
    api.get('auth/health')
      .then(() => setState('ok'))
      .catch(() => setState('down'))
      .finally(() => { done = true; clearTimeout(slow); });
    return () => { done = true; clearTimeout(slow); };
  }, []);
  const { color, text } = STATUS[state];
  return (
    <Box role="status" aria-live="polite" sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 2.5, color: 'text.secondary', fontSize: '0.875rem' }}>
      <Box sx={{
        width: 8, height: 8, borderRadius: '50%', bgcolor: color, flexShrink: 0,
        animation: state === 'waking' || state === 'checking' ? 'status-blink 1.2s ease-in-out infinite' : 'none',
        '@keyframes status-blink': { '50%': { opacity: 0.3 } },
        '@media (prefers-reduced-motion: reduce)': { animation: 'none' },
      }} />
      {text}
    </Box>
  );
}

export default function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const isWide = useMediaQuery({ minWidth: 900 });
  const [form, setForm] = useState({ username: '', password: '' });
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [capsLock, setCapsLock] = useState(false);
  const [busy, setBusy] = useState(false);
  const from = location.state?.from || '/';

  if (user) return <Navigate to={from} replace />;

  const update = (field) => (event) => {
    setForm({ ...form, [field]: event.target.value });
    if (errors[field]) setErrors({ ...errors, [field]: undefined });
  };
  const checkCapsLock = (event) => {
    if (event.getModifierState) setCapsLock(event.getModifierState('CapsLock'));
  };

  async function signIn(username, password) {
    setBusy(true);
    setFormError('');
    try {
      await login(username, password);
      navigate(from, { replace: true });
    } catch (error) {
      setFormError(error.message);
      if (error.details) setErrors(error.details);
      setBusy(false);
    }
  }

  function handleSubmit(event) {
    event.preventDefault();
    const next = {};
    if (!form.username.trim()) next.username = 'Enter your username.';
    if (!form.password) next.password = 'Enter your password.';
    setErrors(next);
    if (Object.keys(next).length === 0) signIn(form.username.trim(), form.password);
  }

  const capsWarning = capsLock && !errors.password;

  return (
    <Box sx={{ minHeight: '100vh', display: 'grid', gridTemplateColumns: isWide ? 'minmax(0, 1.15fr) minmax(0, 1fr)' : '1fr', bgcolor: 'background.default' }}>
      {isWide && (
        <Box component="section" aria-label="About Throughline"
          sx={{ bgcolor: ink, color: '#E6ECF4', p: 8, display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
          <BrandMark color="#FFFFFF" />
          <Box sx={{ maxWidth: 520 }}>
            <Typography component="h1" sx={{ fontSize: '2.75rem', fontWeight: 600, lineHeight: 1.1, letterSpacing: '-0.02em', mb: 2 }}>
              Know where every project stands.
            </Typography>
            <Typography sx={{ color: '#AEBBCD', fontSize: '1.0625rem', mb: 6, maxWidth: 440 }}>
              Milestones, dependencies, people and budgets for every ACME project, with the next action always in view.
            </Typography>
            <RouteIllustration />
          </Box>
          <Typography variant="body2" sx={{ color: '#7F8DA3' }}>ACME Inc. project delivery</Typography>
        </Box>
      )}

      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', p: { xs: 3, sm: 6 } }}>
        <Box sx={{ width: '100%', maxWidth: 400 }}>
          {!isWide && <Box sx={{ mb: 5 }}><BrandMark /></Box>}
          <Typography variant="h2" component={isWide ? 'h2' : 'h1'} gutterBottom>Sign in</Typography>
          <Typography color="text.secondary" sx={{ mb: 4 }}>Use your ACME username and password.</Typography>

          <Box component="form" noValidate onSubmit={handleSubmit}>
            <Stack spacing={2.5}>
              {formError && <Alert severity="error">{formError}</Alert>}
              <TextField label="Username" value={form.username} onChange={update('username')} autoComplete="username"
                autoFocus required disabled={busy} error={Boolean(errors.username)} helperText={errors.username} />
              <TextField label="Password" type={showPassword ? 'text' : 'password'} value={form.password}
                onChange={update('password')} onKeyDown={checkCapsLock} onKeyUp={checkCapsLock} onBlur={() => setCapsLock(false)}
                autoComplete="current-password" required disabled={busy}
                error={Boolean(errors.password)}
                helperText={errors.password || (capsWarning ? (
                  <Box component="span" sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.5, color: 'warning.main', fontWeight: 600 }}>
                    <KeyboardCapslockRounded sx={{ fontSize: 16 }} /> Caps Lock is on
                  </Box>
                ) : undefined)}
                slotProps={{
                  input: {
                    endAdornment: (
                      <InputAdornment position="end">
                        <IconButton edge="end" onClick={() => setShowPassword((value) => !value)}
                          aria-label={showPassword ? 'Hide password' : 'Show password'}>
                          {showPassword ? <VisibilityOffOutlined /> : <VisibilityOutlined />}
                        </IconButton>
                      </InputAdornment>
                    ),
                  },
                }} />
              <Button type="submit" variant="contained" size="large" disabled={busy}>
                {busy ? <CircularProgress size={22} color="inherit" aria-label="Signing in" /> : 'Sign in'}
              </Button>
            </Stack>
          </Box>
          <SystemStatus />

          {SHOW_DEMO && (
            <Box sx={{ mt: 4 }}>
              <Divider sx={{ mb: 2.5 }}>
                <Typography variant="body2" color="text.secondary">Or explore with a demo account</Typography>
              </Divider>
              <Stack spacing={1.25}>
                {DEMO_ACCOUNTS.map((account) => (
                  <Button key={account.role} variant="outlined" color="inherit" disabled={busy}
                    onClick={() => signIn(account.username, account.password)}
                    sx={{ justifyContent: 'flex-start', textAlign: 'left', py: 1.25, px: 2, borderColor: 'divider' }}>
                    <Box>
                      <Typography sx={{ fontWeight: 600 }}>{account.role}</Typography>
                      <Typography variant="body2" color="text.secondary">{account.name}, {account.blurb}</Typography>
                    </Box>
                  </Button>
                ))}
              </Stack>
            </Box>
          )}

          <Box role="note" sx={{ display: 'flex', gap: 1, mt: 4, pt: 2.5, borderTop: 1, borderColor: 'divider' }}>
            <LockOutlined sx={{ fontSize: 16, color: 'text.secondary', mt: '2px' }} />
            <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.8rem', lineHeight: 1.5 }}>
              This system is for authorized ACME users only. Activity is monitored and recorded, and unauthorized
              access is prohibited. Accounts lock for 15 minutes after 5 failed sign-in attempts.
            </Typography>
          </Box>
        </Box>
      </Box>
    </Box>
  );
}