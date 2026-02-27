/**
 * datepicker.js — Initialise Flatpickr on datetime-local inputs.
 *
 * Converts the native browser datetime-local input into a themed
 * Flatpickr calendar that matches the OnTheWay UI.
 */
(function () {
  "use strict";

  function init() {
    if (typeof flatpickr === "undefined") return;

    var inputs = document.querySelectorAll('input[type="datetime-local"]');
    for (var i = 0; i < inputs.length; i++) {
      initPicker(inputs[i]);
    }
  }

  function initPicker(input) {
    // Read any existing value before changing the type
    var existing = input.value;

    // Change type so Flatpickr takes over rendering
    input.type = "text";
    input.readOnly = false;

    flatpickr(input, {
      enableTime: true,
      dateFormat: "Y-m-dTH:i",           // value sent to Django
      altInput: true,
      altFormat: "F j, Y  \\a\\t  h:i K", // human-readable display
      minDate: "today",
      time_24hr: false,
      minuteIncrement: 15,
      defaultDate: existing || null,
      disableMobile: true,                // always use the custom picker
      animate: true
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
