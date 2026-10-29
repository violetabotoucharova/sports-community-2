document.addEventListener("DOMContentLoaded", async () => {
  const link = document.querySelector(".nav__signin");
  if (!link) return;

  const res = await fetch("/api/me");
  const data = await res.json();

  if (data.loggedIn) {
    link.textContent = "SIGN OUT";
    link.href = "#";
    link.addEventListener("click", async (e) => {
      e.preventDefault();
      await fetch("/api/signout", { method: "POST" });
      window.location.href = "/";
    });
  }
});