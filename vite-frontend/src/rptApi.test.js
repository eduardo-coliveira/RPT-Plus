import { afterEach, describe, expect, it, vi } from 'vitest';
import { recordAction } from './rptApi.js';

describe('action logging API', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    sessionStorage.clear();
  });

  it('sends the server-issued session token with action logs', async () => {
    sessionStorage.setItem('loggedInSessionToken', 'session-token');
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      json: async () => ({ status: 'ok' }),
    }));
    const payload = { username: 'learner', exercise: '0.isOvenReady', action: 'Diagnose' };

    await recordAction(payload);

    expect(fetch).toHaveBeenCalledWith('/rpt-plus/log_action', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Session-Token': 'session-token',
      },
      body: JSON.stringify(payload),
    });
  });
});
