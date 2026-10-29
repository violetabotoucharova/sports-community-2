async function api(url, options = {}) {
  const opts = { credentials: "same-origin", ...options };
  if (opts.body && !(opts.body instanceof FormData)) {
    opts.headers = { "Content-Type": "application/json", ...(opts.headers || {}) };
    opts.body = JSON.stringify(opts.body);
  }
  try {
    const res = await fetch(url, opts);
    let data = {};
    try { data = await res.json(); } catch (e) {}
    if (res.status === 401) window.location.href = "/signin.html";
    return { ok: res.ok, status: res.status, data };
  } catch (e) {
    return { ok: false, status: 0, data: { error: "Could not reach the server." } };
  }
}

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

function avatar(user, cls = "avatar") {
  if (user.avatar_url) return `<img class="${cls}" src="${esc(user.avatar_url)}" alt="" />`;
  return `<span class="${cls} avatar--letter">${esc(user.username.charAt(0).toUpperCase())}</span>`;
}

function formatDate(iso) {
  return new Date(iso).toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
}

function showMessage(el, text, isError = true) {
  el.textContent = text;
  el.className = "msg " + (isError ? "msg--error" : "msg--ok");
}

function renderNav() {
  document.getElementById("nav-root").innerHTML = `
    <nav>
      <div class="nav__bar">
        <div class="nav__header">
          <div class="nav__logo"><a href="/"><img src="/logoprimary.svg" alt="logo" /></a></div>
          <div class="nav__menu__btn" id="menu-btn"><i class="ri-menu-line"></i></div>
        </div>
        <ul class="nav__links" id="nav-links">
          <li><a href="/activities.html">Find activities</a></li>
          <li><a href="/create-activity.html">Create activity</a></li>
          <li><a href="/profile.html">My profile</a></li>
          <li><a href="#" class="nav__signin" id="signout">SIGN OUT</a></li>
        </ul>
      </div>
    </nav>`;

  const menuBtn = document.getElementById("menu-btn");
  const navLinks = document.getElementById("nav-links");
  const icon = menuBtn.querySelector("i");

  menuBtn.addEventListener("click", () => {
    navLinks.classList.toggle("open");
    icon.className = navLinks.classList.contains("open") ? "ri-close-line" : "ri-menu-line";
  });

  document.getElementById("signout").addEventListener("click", async (e) => {
    e.preventDefault();
    await fetch("/api/signout", { method: "POST" });
    window.location.href = "/";
  });
}