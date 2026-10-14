import { beforeEach, describe, expect, it, vi } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes } from 'react-router-dom';
import LoginPage from './LoginPage';
import { auth } from '../services/api';
import { jsonResponse, renderWithProviders } from '../test/render';

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
  beforeEach(() => {
    globalThis.fetch = vi.fn();
  });

  it('shows an error next to each empty field and does not call the server', async () => {
    renderLogin();
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(screen.getByText('Enter your username.')).toBeInTheDocument();
    expect(screen.getByText('Enter your password.')).toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalled();
  });

  it("shows the server's message when the password is wrong", async () => {
    fetch.mockResolvedValueOnce(jsonResponse(401, { error: { code: 'INVALID_CREDENTIALS', message: 'Incorrect username or password.' } }));
    renderLogin();
    await userEvent.type(screen.getByLabelText(/^username/i), 'admin');
    await userEvent.type(screen.getByLabelText(/^password/i), 'wrong-password1');
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(await screen.findByText('Incorrect username or password.')).toBeInTheDocument();
    expect(auth.get()).toBeNull();
  });

  it('signs in with a demo account and lands on the dashboard', async () => {
    fetch.mockResolvedValueOnce(jsonResponse(200, {
      access_token: 'a', refresh_token: 'r', token_type: 'Bearer', expires_in: 900,
      user: { id: 2, name: 'Dana Whitfield', username: 'dana.whitfield', role: 'manager' },
    }));
    renderLogin();
    await userEvent.click(screen.getByRole('button', { name: /manager/i }));
    expect(await screen.findByText('Dashboard home')).toBeInTheDocument();
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ username: 'dana.whitfield', password: 'Demo1234!' });
    expect(auth.get().user.name).toBe('Dana Whitfield');
  });

  it('lets people reveal the password they typed', async () => {
    renderLogin();
    const password = screen.getByLabelText(/^password/i);
    expect(password).toHaveAttribute('type', 'password');
    await userEvent.click(screen.getByRole('button', { name: 'Show password' }));
    expect(password).toHaveAttribute('type', 'text');
  });
});