function showAppShell() {
  const nav = document.querySelector("nav");
  const main = document.querySelector("main");
  if (nav) nav.style.display = "";
  if (main) main.style.display = "";
}

function setLoginMessage(text, isError = true) {
  const message = document.getElementById("loginMessage");
  if (!message) return;
  message.textContent = text;
  message.style.color = isError
    ? "var(--md-sys-color-error)"
    : "var(--md-sys-color-on-surface)";
}

async function handleLoginSubmit(event) {
  event.preventDefault();
  setLoginMessage("");

  const username = document.getElementById("loginUsername")?.value.trim();
  const password = document.getElementById("loginPassword")?.value;
  const button = event.currentTarget.querySelector("button");

  if (!username || !password) {
    setLoginMessage("Please enter both username and password.");
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
      setLoginMessage(error.detail || "Login failed.");
      return;
    }

    const user = await response.json();
    window.currentUser = user;
    document.getElementById("loginOverlay").style.display = "none";
    showAppShell();

    if (typeof window.startApp === "function") {
      window.startApp();
    }
  } catch (error) {
    setLoginMessage(error.message || "Login failed.");
  } finally {
    button.disabled = false;
    button.textContent = "Login";
  }
}

export function initLogin() {
  const form = document.getElementById("loginForm");
  form?.addEventListener("submit", handleLoginSubmit);
}

window.initLogin = initLogin;
document.addEventListener("DOMContentLoaded", initLogin);