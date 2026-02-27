/**
 * Address autocomplete powered by Nominatim (OpenStreetMap).
 *
 * Attach to any <input> with data-autocomplete="address".
 * Optional attrs:
 *   data-state-target="<id>"  - auto-fill a state field
 *   data-lat-target="<id>"    - auto-fill a hidden lat field
 *   data-lng-target="<id>"    - auto-fill a hidden lng field
 */
(function () {
  "use strict";

  var NOMINATIM_URL = "https://nominatim.openstreetmap.org/search";
  var DEBOUNCE_MS = 400;
  var MIN_CHARS = 3;

  var STATE_CODES = {
    "Alabama":"AL","Alaska":"AK","Arizona":"AZ","Arkansas":"AR","California":"CA",
    "Colorado":"CO","Connecticut":"CT","Delaware":"DE","Florida":"FL","Georgia":"GA",
    "Hawaii":"HI","Idaho":"ID","Illinois":"IL","Indiana":"IN","Iowa":"IA","Kansas":"KS",
    "Kentucky":"KY","Louisiana":"LA","Maine":"ME","Maryland":"MD","Massachusetts":"MA",
    "Michigan":"MI","Minnesota":"MN","Mississippi":"MS","Missouri":"MO","Montana":"MT",
    "Nebraska":"NE","Nevada":"NV","New Hampshire":"NH","New Jersey":"NJ","New Mexico":"NM",
    "New York":"NY","North Carolina":"NC","North Dakota":"ND","Ohio":"OH","Oklahoma":"OK",
    "Oregon":"OR","Pennsylvania":"PA","Rhode Island":"RI","South Carolina":"SC",
    "South Dakota":"SD","Tennessee":"TN","Texas":"TX","Utah":"UT","Vermont":"VT",
    "Virginia":"VA","Washington":"WA","West Virginia":"WV","Wisconsin":"WI","Wyoming":"WY",
    "District of Columbia":"DC"
  };

  function stateCode(name) {
    if (!name) return "";
    if (name.length === 2) return name.toUpperCase();
    return STATE_CODES[name] || "";
  }

  function debounce(fn, ms) {
    var timer;
    return function () {
      var ctx = this, args = arguments;
      clearTimeout(timer);
      timer = setTimeout(function () { fn.apply(ctx, args); }, ms);
    };
  }

  function setById(id, val) {
    if (!id) return;
    var el = document.getElementById(id);
    if (el) el.value = val;
  }

  function buildList(input) {
    var list = document.createElement("div");
    list.className = "ac-list";
    input.parentNode.style.position = "relative";
    input.parentNode.appendChild(list);
    return list;
  }

  function clearList(list) {
    list.innerHTML = "";
    list.style.display = "none";
  }

  function initInput(input) {
    var list = buildList(input);
    var stateTargetId = input.getAttribute("data-state-target");
    var latTargetId   = input.getAttribute("data-lat-target");
    var lngTargetId   = input.getAttribute("data-lng-target");

    var fetchSuggestions = debounce(function () {
      var q = input.value.trim();
      if (q.length < MIN_CHARS) { clearList(list); return; }

      var url = NOMINATIM_URL +
        "?q=" + encodeURIComponent(q) +
        "&format=json&addressdetails=1&limit=5&countrycodes=us" +
        "&email=handyrides@example.com";

      fetch(url, {
        headers: { "Accept": "application/json" },
        mode: "cors"
      })
        .then(function (r) {
          if (!r.ok) {
            console.warn("Nominatim returned", r.status, r.statusText);
            return [];
          }
          return r.json();
        })
        .then(function (data) {
          clearList(list);
          if (!data || !data.length) return;

          data.forEach(function (place) {
            var item = document.createElement("div");
            item.className = "ac-item";
            item.textContent = place.display_name;

            item.addEventListener("mousedown", function (e) {
              e.preventDefault();
              input.value = place.display_name;
              clearList(list);

              // Auto-fill state
              if (stateTargetId && place.address) {
                var code = stateCode(place.address.state);
                if (code) setById(stateTargetId, code);
              }

              // Auto-fill lat/lng
              if (place.lat && place.lon) {
                setById(latTargetId, place.lat);
                setById(lngTargetId, place.lon);
              }

              // Fire custom event so the live map can update
              input.dispatchEvent(new CustomEvent("address-selected", {
                bubbles: true,
                detail: {
                  display_name: place.display_name,
                  lat: parseFloat(place.lat),
                  lng: parseFloat(place.lon),
                  address: place.address || {}
                }
              }));
            });

            list.appendChild(item);
          });

          list.style.display = "block";
        })
        .catch(function (err) {
          console.warn("Autocomplete fetch error:", err);
          clearList(list);
        });
    }, DEBOUNCE_MS);

    input.addEventListener("input", fetchSuggestions);
    input.addEventListener("focus", function () {
      if (input.value.trim().length >= MIN_CHARS) fetchSuggestions();
    });
    input.addEventListener("blur", function () {
      setTimeout(function () { clearList(list); }, 200);
    });
  }

  function init() {
    var inputs = document.querySelectorAll('[data-autocomplete="address"]');
    for (var i = 0; i < inputs.length; i++) initInput(inputs[i]);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
