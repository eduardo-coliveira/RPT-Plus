/** Handle login and session cleanup for the application. */

/** Show the application after login. */
function showAuthenticatedApp() {
  const nav = document.querySelector("nav");
  const main = document.querySelector("main");
  if (nav) nav.style.display = "";
  if (main) main.style.display = "";
}

/** Show a login status message. */
function displayLoginMessage(text, isError = true) {
  const message = document.getElementById("loginMessage");
  if (!message) return;
  message.textContent = text;
  message.style.color = isError
    ? "var(--md-sys-color-error)"
    : "var(--md-sys-color-on-surface)";
}

/** Submit credentials, start the user session, and start the tutor app. */
async function submitLogin(event) {
  event.preventDefault();
  displayLoginMessage("");

  const username = document.getElementById("loginUsername")?.value.trim();
  const password = document.getElementById("loginPassword")?.value;
  const button = event.currentTarget.querySelector("button");

  if (!username || !password) {
    displayLoginMessage("Please enter both username and password.");
    return;
  }

  button.disabled = true;
  button.textContent = "Signing in...";

  try {
    const response = await fetch("/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });

    if (!response.ok) {
      const error = await response.json();
      displayLoginMessage(error.detail || "Login failed.");
      return;
    }

    const user = await response.json();
    window.currentUser = user;
    sessionStorage.setItem('loggedInUser', user.username);
    document.getElementById("loginOverlay").style.display = "none";
    showAuthenticatedApp();

    if (typeof window.startApp === "function") {
      window.startApp();
    }
  } catch (error) {
    displayLoginMessage(error.message || "Login failed.");
  } finally {
    button.disabled = false;
    button.textContent = "Login";
  }
}

/** Register the login and unload handlers. */
export function initializeLogin() {
  const form = document.getElementById("loginForm");
  form?.addEventListener("submit", submitLogin);

  window.addEventListener('beforeunload', () => {
    const loggedInUser = sessionStorage.getItem('loggedInUser');
    if (loggedInUser) {
      const blob = new Blob(
        [JSON.stringify({ username: loggedInUser })],
        { type: 'application/json' }
      );
      navigator.sendBeacon('/logout', blob);
    }
  });

}

window.initializeLogin = initializeLogin;
document.addEventListener("DOMContentLoaded", initializeLogin);