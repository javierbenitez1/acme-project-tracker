import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes } from 'react-router-dom';
import LoginPage from './LoginPage';
import { auth } from '../services/api';
import { jsonResponse, renderWithProviders } from '../test/render';

/** A fake server: the status check always succeeds, and sign-in calls get the queued responses in order. */
function fakeServer(...signInResponses) {
  globalThis.fetch = vi.fn((url) => Promise.resolve(
    String(url).includes('auth/health') ? jsonResponse(200, { status: 'ok' }) : signInResponses.shift(),
  ));
}
const signInCalls = () => fetch.mock.calls.filter(([url]) => String(url).includes('auth/login'));

function renderLogin() {
  return renderWithProviders(
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<p>Dashboard home</p>} />
    </Routes>,
    { route: '/login' },
  );
}

describe('Login page', () => {
  beforeEach(() => fakeServer());

  it('shows an error next to each empty field and does not call the server', async () => {
    renderLogin();
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(screen.getByText('Enter your username.')).toBeInTheDocument();
    expect(screen.getByText('Enter your password.')).toBeInTheDocument();
    expect(signInCalls()).toHaveLength(0);
  });

  it("shows the server's message when the password is wrong", async () => {
    fakeServer(jsonResponse(401, { error: { code: 'INVALID_CREDENTIALS', message: 'Incorrect username or password.' } }));
    renderLogin();
    await userEvent.type(screen.getByLabelText(/^username/i), 'admin');
    await userEvent.type(screen.getByLabelText(/^password/i), 'wrong-password1');
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(await screen.findByText('Incorrect username or password.')).toBeInTheDocument();
    expect(auth.get()).toBeNull();
  });

  it('explains a locked account', async () => {
    fakeServer(jsonResponse(423, { error: { code: 'ACCOUNT_LOCKED', message: 'Too many failed sign-in attempts. Try again in 15 minutes.' } }));
    renderLogin();
    await userEvent.type(screen.getByLabelText(/^username/i), 'admin');
    await userEvent.type(screen.getByLabelText(/^password/i), 'Admin123!');
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(await screen.findByText(/Too many failed sign-in attempts/)).toBeInTheDocument();
  });

  it('signs in with a demo account and lands on the dashboard', async () => {
    fakeServer(jsonResponse(200, {
      access_token: 'a', refresh_token: 'r', token_type: 'Bearer', expires_in: 900,
      user: { id: 2, name: 'Dana Whitfield', username: 'dana.whitfield', role: 'manager' },
    }));
    renderLogin();
    await userEvent.click(screen.getByRole('button', { name: /manager/i }));
    expect(await screen.findByText('Dashboard home')).toBeInTheDocument();
    expect(JSON.parse(signInCalls()[0][1].body)).toEqual({ username: 'dana.whitfield', password: 'Demo1234!' });
    expect(auth.get().user.name).toBe('Dana Whitfield');
  });

  it('lets people reveal the password they typed', async () => {
    renderLogin();
    const password = screen.getByLabelText(/^password/i);
    expect(password).toHaveAttribute('type', 'password');
    await userEvent.click(screen.getByRole('button', { name: 'Show password' }));
    expect(password).toHaveAttribute('type', 'text');
  });

  it('warns when Caps Lock is on', () => {
    renderLogin();
    const password = screen.getByLabelText(/^password/i);
    fireEvent.keyDown(password, { key: 'A', modifierCapsLock: true });
    expect(screen.getByText('Caps Lock is on')).toBeInTheDocument();
    fireEvent.keyDown(password, { key: 'a', modifierCapsLock: false });
    expect(screen.queryByText('Caps Lock is on')).not.toBeInTheDocument();
  });

  it('checks the system status and shows the system-use notice', async () => {
    renderLogin();
    expect(await screen.findByText('All systems operational')).toBeInTheDocument();
    expect(screen.getByText(/authorized ACME users only/)).toBeInTheDocument();
  });
});