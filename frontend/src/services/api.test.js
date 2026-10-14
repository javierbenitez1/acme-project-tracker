import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { api, auth } from './api';
import { jsonResponse } from '../test/render';

const SESSION = { access_token: 'old-access', refresh_token: 'refresh-1', user: { id: 1, name: 'Dana', role: 'manager' } };

describe('API client', () => {
  beforeEach(() => {
    auth.set(null);
    globalThis.fetch = vi.fn();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it('sends the access token with every request', async () => {
    auth.set(SESSION);
    fetch.mockResolvedValueOnce(jsonResponse(200, []));
    await api.get('projects');
    expect(fetch.mock.calls[0][0]).toMatch(/\/api\/projects$/);
    expect(fetch.mock.calls[0][1].headers.Authorization).toBe('Bearer old-access');
  });

  it('refreshes an expired token once and retries the request', async () => {
    auth.set(SESSION);
    fetch
      .mockResolvedValueOnce(jsonResponse(401, { error: { code: 'TOKEN_EXPIRED', message: 'Expired' } }))
      .mockResolvedValueOnce(jsonResponse(200, { ...SESSION, access_token: 'new-access', refresh_token: 'refresh-2' }))
      .mockResolvedValueOnce(jsonResponse(200, [{ id: 7 }]));

    await expect(api.get('projects')).resolves.toEqual([{ id: 7 }]);
    expect(fetch.mock.calls[1][0]).toMatch(/\/api\/auth\/refresh$/);
    expect(fetch.mock.calls[2][1].headers.Authorization).toBe('Bearer new-access');
    expect(auth.get().refresh_token).toBe('refresh-2');
  });

  it('signs the user out when their token is no longer valid', async () => {
    auth.set(SESSION);
    fetch.mockResolvedValueOnce(jsonResponse(401, { error: { code: 'TOKEN_INVALID', message: 'Invalid token' } }));
    await expect(api.get('projects')).rejects.toMatchObject({ status: 401, code: 'TOKEN_INVALID' });
    expect(auth.get()).toBeNull();
  });

  it('turns server errors into readable messages with field details', async () => {
    fetch.mockResolvedValueOnce(jsonResponse(400, {
      error: { code: 'VALIDATION_ERROR', message: 'Some fields are invalid.', details: { name: 'This field is required.' } },
    }));
    await expect(api.post('projects', {})).rejects.toMatchObject({
      status: 400, message: 'Some fields are invalid.', details: { name: 'This field is required.' },
    });
  });

  it('returns null for 204 No Content', async () => {
    fetch.mockResolvedValueOnce(new Response(null, { status: 204 }));
    await expect(api.delete('budgets/3')).resolves.toBeNull();
  });

  it('explains when the network is down', async () => {
    fetch.mockRejectedValueOnce(new TypeError('Failed to fetch'));
    await expect(api.get('projects')).rejects.toMatchObject({ status: 0, message: expect.stringContaining("Can't reach the server") });
  });

  it('retries a save while the database wakes up (503 means nothing was saved)', async () => {
    vi.useFakeTimers();
    fetch
      .mockResolvedValueOnce(jsonResponse(503, { error: { code: 'DATABASE_UNAVAILABLE', message: 'Waking up' } }))
      .mockResolvedValueOnce(jsonResponse(201, { id: 9 }));
    const request = api.post('actions', { title: 'Call the vendor' });
    await vi.advanceTimersByTimeAsync(3000);
    await expect(request).resolves.toEqual({ id: 9 });
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it('never retries a save that timed out at the gateway, to avoid duplicates', async () => {
    fetch.mockResolvedValueOnce(new Response('<html>Gateway timeout</html>', { status: 504 }));
    await expect(api.post('actions', { title: 'Call the vendor' })).rejects.toMatchObject({
      status: 504, message: expect.stringContaining('waking up'),
    });
    expect(fetch).toHaveBeenCalledTimes(1);
  });
});