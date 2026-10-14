import { useState } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { useMediaQuery } from 'react-responsive';
import {
  Alert, Box, Button, CircularProgress, Divider, IconButton, InputAdornment, Stack, TextField, Typography,
} from '@mui/material';
import VisibilityOutlined from '@mui/icons-material/VisibilityOutlined';
import VisibilityOffOutlined from '@mui/icons-material/VisibilityOffOutlined';
import { useAuth } from '../auth/AuthContext';
import BrandMark from '../components/BrandMark';
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

function RouteIllustration() {
  return (
    <Box component="svg" viewBox="0 0 410 120" role="img" aria-label="A project moving through four milestones, currently in Build"
      sx={{ width: '100%', maxWidth: 440, display: 'block' }}>
      <line x1="40" y1="56" x2="260" y2="56" stroke="#4FB3B1" strokeWidth="6" strokeLinecap="round" />
      <line x1="260" y1="56" x2="370" y2="56" stroke="#3A4A63" strokeWidth="6" strokeLinecap="round" strokeDasharray="1 12" />
      <circle className="station-pulse" cx="260" cy="56" r="13" fill="none" stroke="#E0A935" strokeWidth="3" />
      {STATIONS.map((station) => (
        <g key={station.label}>
          <circle cx={station.x} cy="56" r={station.state === 'current' ? 13 : 10} fill={ink}
            stroke={STATION_STROKE[station.state]} strokeWidth="5" />
          <text x={station.x} y="100" textAnchor="middle" fill={station.state === 'next' ? '#7F8DA3' : '#C9D3E1'} fontSize="13">
            {station.label}
          </text>
        </g>
      ))}
      <text x="260" y="24" textAnchor="middle" fill="#E0A935" fontSize="12" fontWeight="600">Today</text>
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
  const [busy, setBusy] = useState(false);
  const from = location.state?.from || '/';

  if (user) return <Navigate to={from} replace />;

  const update = (field) => (event) => {
    setForm({ ...form, [field]: event.target.value });
    if (errors[field]) setErrors({ ...errors, [field]: undefined });
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
                onChange={update('password')} autoComplete="current-password" required disabled={busy}
                error={Boolean(errors.password)} helperText={errors.password}
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

          {SHOW_DEMO && (
            <Box sx={{ mt: 5 }}>
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
        </Box>
      </Box>
    </Box>
  );
}