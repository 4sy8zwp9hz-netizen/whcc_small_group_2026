// Progressive enhancement: ordinary form submissions still work without JavaScript.
document.documentElement.classList.add("js");
let saving = false;

async function saveAttendance(form, action, focusMember) {
  if (saving || !form.reportValidity()) return;
  const data = new FormData(form);
  data.set("action", action);
  saving = true;
  const status = document.getElementById("attendance-feedback");
  status.textContent = "Saving attendance…";
  document.querySelectorAll(".rsvp-form input, .rsvp-form button").forEach(el => { el.disabled = true; });
  const error = form.querySelector(".rsvp-error");
  error.textContent = "";
  try {
    const response = await fetch(form.getAttribute("action"), {
      method: "POST", body: data, headers: {Accept: "application/json"}, credentials: "same-origin"
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Your response could not be saved.");
    const selectedKey = form.closest(".rsvp-panel").dataset.meeting;
    document.querySelectorAll(".rsvp-panel").forEach(panel => {
      const html = result.panels[panel.dataset.meeting];
      if (html) panel.outerHTML = html;
    });
    status.textContent = result.message;
    const panel = [...document.querySelectorAll(".rsvp-panel")].find(el => el.dataset.meeting === selectedKey);
    if (panel) {
      const target = focusMember
        ? [...panel.querySelectorAll('input[name="attending"]')].find(el => el.value === focusMember)
        : [...panel.querySelectorAll('button[name="action"]')].find(el => el.value === action);
      target?.focus({preventScroll: true});
    }
  } catch (failure) {
    // Restore the last rendered checkbox state; never imply a failed update was saved.
    form.querySelectorAll('input[type="checkbox"]').forEach(el => { el.checked = el.defaultChecked; });
    error.textContent = failure instanceof SyntaxError
      ? "Your response could not be saved. Reload the page and try again."
      : failure.message || "Connection lost. Please try again.";
    status.textContent = "Attendance was not saved.";
  } finally {
    saving = false;
    document.querySelectorAll(".rsvp-form input, .rsvp-form button").forEach(el => { el.disabled = false; });
  }
}

document.addEventListener("submit", event => {
  const form = event.target;
  if (!form.matches(".rsvp-form")) return;
  event.preventDefault();
  saveAttendance(form, event.submitter?.value || "custom");
});
document.addEventListener("change", event => {
  if (!event.target.matches('.rsvp-form input[name="attending"]')) return;
  saveAttendance(event.target.form, "custom", event.target.value);
});
