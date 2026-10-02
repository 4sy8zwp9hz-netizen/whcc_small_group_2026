"use strict";
document.querySelectorAll(".assignment-picker").forEach(picker => {
  const field = picker.dataset.field;
  const mode = picker.querySelector(`[name="use_choices_${field}"]`);
  const custom = picker.querySelector(`[name="${field}"]`);
  const display = picker.querySelector(".assignment-value");
  picker.querySelector(".picker-mode").hidden = true;
  picker.querySelectorAll(`[name="choices_${field}"]`).forEach(box => {
    box.addEventListener("change", () => {
      mode.checked = true;
      const names = Array.from(picker.querySelectorAll(`[name="choices_${field}"]:checked`), item => item.dataset.display);
      custom.value = names.join(" / ");
      display.textContent = custom.value || "Choose assignments";
    });
  });
  custom.addEventListener("input", () => {
    mode.checked = false;
    display.textContent = custom.value || "Choose assignments";
  });
});
