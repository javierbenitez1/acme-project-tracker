import { createTheme } from '@mui/material/styles';

/** Health colors are used everywhere a project or milestone shows its state, always with a text label. */
export const health = {
  on_track: { label: 'On track', color: '#2F8F5B' },
  at_risk: { label: 'At risk', color: '#C98A12' },
  off_track: { label: 'Off track', color: '#C2412D' },
  completed: { label: 'Completed', color: '#5A6B85' },
  archived: { label: 'Archived', color: '#8A94A6' },
};

export const ink = '#142033';

const fontFamily = '"IBM Plex Sans", system-ui, -apple-system, "Segoe UI", sans-serif';

export const theme = createTheme({
  cssVariables: { colorSchemeSelector: 'data' },
  colorSchemes: {
    light: {
      palette: {
        primary: { main: '#0B6E6E', light: '#3C9A99', dark: '#064B4B', contrastText: '#FFFFFF' },
        secondary: { main: '#2445C8' },
        success: { main: health.on_track.color },
        warning: { main: health.at_risk.color },
        error: { main: health.off_track.color },
        background: { default: '#F3F5F8', paper: '#FFFFFF' },
        text: { primary: '#142033', secondary: '#526075' },
        divider: '#DCE2EA',
      },
    },
    dark: {
      palette: {
        primary: { main: '#4FB3B1', contrastText: '#06201F' },
        secondary: { main: '#8FA6FF' },
        success: { main: '#56B583' },
        warning: { main: '#E0A935' },
        error: { main: '#E06A55' },
        background: { default: '#0D1522', paper: '#141F31' },
        text: { primary: '#E6ECF4', secondary: '#9AA8BC' },
        divider: '#253248',
      },
    },
  },
  shape: { borderRadius: 8 },
  typography: {
    fontFamily,
    h1: { fontSize: '2rem', fontWeight: 600, letterSpacing: '-0.015em', lineHeight: 1.2 },
    h2: { fontSize: '1.5rem', fontWeight: 600, letterSpacing: '-0.01em', lineHeight: 1.25 },
    h3: { fontSize: '1.125rem', fontWeight: 600, lineHeight: 1.35 },
    h4: { fontSize: '1rem', fontWeight: 600, lineHeight: 1.4 },
    subtitle1: { fontWeight: 500 },
    body1: { fontSize: '0.9375rem', lineHeight: 1.55 },
    body2: { fontSize: '0.875rem', lineHeight: 1.5 },
    button: { textTransform: 'none', fontWeight: 600 },
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: { fontVariantNumeric: 'tabular-nums' },
        ':focus-visible': { outline: '2px solid #2445C8', outlineOffset: 2 },
        '@media (prefers-reduced-motion: reduce)': {
          '*, *::before, *::after': { animationDuration: '0.01ms !important', transitionDuration: '0.01ms !important' },
        },
      },
    },
    MuiButton: { defaultProps: { disableElevation: true }, styleOverrides: { root: { borderRadius: 8 } } },
    MuiCard: { defaultProps: { variant: 'outlined' }, styleOverrides: { root: { borderRadius: 12 } } },
    MuiPaper: { defaultProps: { elevation: 0 } },
    MuiChip: { styleOverrides: { root: { borderRadius: 6, fontWeight: 600 } } },
    MuiTextField: { defaultProps: { fullWidth: true } },
  },
});