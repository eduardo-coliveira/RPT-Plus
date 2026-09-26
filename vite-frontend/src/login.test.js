import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { initLogin } from './login.js';

describe('login form', () => {
  let beforeUnloadHandlers;

  beforeEach(() => {
    document.body.innerHTML = `
      <div id="loginOverlay">
        <form id="loginForm">
          <input id="loginUsername" />
          <input id="loginPassword" />
          <button type="submit">Login</button>
          <div id="loginMessage"></div>
        </form>
      </div>
      <nav style="display: none"></nav>
      <main style="display: none"></main>
    `;
    sessionStorage.clear();
    window.startApp = vi.fn();
    vi.stubGlobal('fetch', vi.fn());
    beforeUnloadHandlers = [];
    const addEventListener = window.addEventListener.bind(window);
    vi.spyOn(window, 'addEventListener').mockImplementation((type, listener, options) => {
      if (type === 'beforeunload') beforeUnloadHandlers.push(listener);
      return addEventListener(type, listener, options);
    });
    initLogin();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    delete window.startApp;
    delete window.currentUser;
  });

  function submitLoginForm() {
    document.getElementById('loginForm').dispatchEvent(
      new Event('submit', { bubbles: true, cancelable: true }),
    );
  }

  it('stores the user and opens the app after a successful login', async () => {
    fetch.mockResolvedValue({
      ok: true,
      json: async () => ({ username: 'learner', group: 'group-a' }),
    });
    document.getElementById('loginUsername').value = ' learner ';
    document.getElementById('loginPassword').value = 'secret';

    submitLoginForm();

    await vi.waitFor(() => expect(window.startApp).toHaveBeenCalledOnce());

    expect(fetch).toHaveBeenCalledWith('/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: 'learner', password: 'secret' }),
    });
    expect(sessionStorage.getItem('loggedInUser')).toBe('learner');
    expect(document.getElementById('loginOverlay').style.display).toBe('none');
    expect(document.querySelector('nav').style.display).toBe('');
    expect(document.querySelector('main').style.display).toBe('');
    expect(document.querySelector('button').disabled).toBe(false);
  });

  it('shows the server error and keeps the login form visible', async () => {
    fetch.mockResolvedValue({
      ok: false,
      json: async () => ({ detail: 'Invalid username or password' }),
    });
    document.getElementById('loginUsername').value = 'learner';
    document.getElementById('loginPassword').value = 'wrong';

    submitLoginForm();

    await vi.waitFor(() => {
      expect(document.getElementById('loginMessage').textContent).toBe(
        'Invalid username or password',
      );
    });

    expect(sessionStorage.getItem('loggedInUser')).toBeNull();
    expect(document.getElementById('loginOverlay').style.display).not.toBe('none');
    expect(window.startApp).not.toHaveBeenCalled();
    expect(document.querySelector('button').disabled).toBe(false);
  });

  it('sends a logout beacon for the stored user on page unload', () => {
    sessionStorage.setItem('loggedInUser', 'learner');
    const sendBeacon = vi.fn();
    vi.stubGlobal('navigator', { sendBeacon });
    vi.stubGlobal('Blob', class TestBlob {
      constructor(parts, options) {
        this.parts = parts;
        this.type = options.type;
      }
    });

    beforeUnloadHandlers.at(-1)(new Event('beforeunload'));

    expect(sendBeacon).toHaveBeenCalledOnce();
    expect(sendBeacon).toHaveBeenCalledWith('/logout', {
      parts: ['{"username":"learner"}'],
      type: 'application/json',
    });
  });
});