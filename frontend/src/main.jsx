import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import CssBaseline from '@mui/material/CssBaseline';
import { ThemeProvider } from '@mui/material/styles';
import '@fontsource/ibm-plex-sans/400.css';
import '@fontsource/ibm-plex-sans/500.css';
import '@fontsource/ibm-plex-sans/600.css';
import '@fontsource/ibm-plex-sans/700.css';
import './index.css';
import { theme } from './theme';
import { AuthProvider } from './auth/AuthContext';
import { ToastProvider } from './components/Toast';
import App from './App';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 15_000,
      refetchOnWindowFocus: true,
      retry: (failureCount, error) => (error?.status === 0 || error?.status >= 500) && failureCount < 2,
    },
  },
});

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ThemeProvider theme={theme} defaultMode="light">
      <CssBaseline />
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <AuthProvider>
            <ToastProvider>
              <App />
            </ToastProvider>
          </AuthProvider>
        </BrowserRouter>
      </QueryClientProvider>
    </ThemeProvider>
  </StrictMode>,
);
// Installable app: register the service worker in production builds only, so local development never caches.
if ('serviceWorker' in navigator && import.meta.env.PROD) {
  window.addEventListener('load', () => { navigator.serviceWorker.register('/sw.js', { updateViaCache: 'none' }).catch(() => {}); });
}

// New version check: when the tab comes back into view (and every 5 minutes), compare the deployed
// build with the one running here, and offer a reload instead of leaving people on an old version.
function runningBuild() {
  const script = document.querySelector('script[type="module"][src*="/assets/index-"]');
  return script ? new URL(script.src).pathname : null;
}

function showUpdateBanner() {
  const banner = document.createElement('div');
  banner.id = 'update-banner';
  banner.setAttribute('role', 'status');
  banner.style.cssText = 'position:fixed;left:50%;bottom:88px;transform:translateX(-50%);z-index:2000;'
    + 'display:flex;gap:12px;align-items:center;padding:10px 12px 10px 16px;border-radius:10px;'
    + 'background:#142033;color:#fff;font-family:"IBM Plex Sans",system-ui,sans-serif;font-size:14px;'
    + 'box-shadow:0 6px 24px rgba(0,0,0,.3);max-width:calc(100vw - 32px)';
  banner.textContent = 'A new version of Throughline is available.';
  const button = document.createElement('button');
  button.type = 'button';
  button.textContent = 'Reload';
  button.style.cssText = 'border:0;border-radius:6px;padding:6px 12px;background:#4FB3B1;color:#142033;'
    + 'font-family:inherit;font-size:14px;font-weight:700;cursor:pointer';
  button.addEventListener('click', () => window.location.reload());
  banner.append(button);
  document.body.append(banner);
}

async function checkForNewVersion() {
  const running = runningBuild();
  if (!running || document.getElementById('update-banner')) return;
  try {
    const html = await (await fetch('/', { cache: 'no-store' })).text();
    const deployed = html.match(/\/assets\/index-[\w-]+\.js/)?.[0];
    if (deployed && deployed !== running) showUpdateBanner();
  } catch {
    // Offline right now: try again next time.
  }
}

if (import.meta.env.PROD) {
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') checkForNewVersion();
  });
  setInterval(checkForNewVersion, 5 * 60 * 1000);
}
