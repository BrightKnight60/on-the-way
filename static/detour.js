/**
 * detour.js — Async OSRM detour refinement for search results.
 *
 * After the search page loads, this script finds all ride cards that
 * have detour check data and calls OSRM to compute precise detour times.
 * Results are displayed in-place, replacing the geometry-based estimates.
 *
 * Throttles requests to ~1/sec to respect the OSRM public server rate limit.
 */
(function () {
  "use strict";

  var OSRM_URL = "https://router.project-osrm.org/route/v1/driving/";
  var THROTTLE_MS = 1100; // slightly over 1 second

  function init() {
    var cards = document.querySelectorAll("[data-detour-check]");
    if (!cards.length) return;

    // Parse rider coordinates from the page
    var riderEl = document.getElementById("rider-coords");
    if (!riderEl) return;

    var rider;
    try { rider = JSON.parse(riderEl.textContent); } catch (e) { return; }
    if (!rider.lat || !rider.lng || !rider.dest_lat || !rider.dest_lng) return;

    // Queue up all cards that need detour refinement
    var queue = [];
    for (var i = 0; i < cards.length; i++) {
      var card = cards[i];
      var data;
      try { data = JSON.parse(card.getAttribute("data-detour-check")); } catch (e) { continue; }
      queue.push({ card: card, data: data });
    }

    // Process queue with throttling
    processQueue(queue, rider, 0);
  }

  function processQueue(queue, rider, index) {
    if (index >= queue.length) return;

    var item = queue[index];
    var d = item.data;

    // Build OSRM request: driver origin -> rider pickup -> rider dropoff -> driver dest
    var coords = d.origin_lng + "," + d.origin_lat + ";" +
                 rider.lng + "," + rider.lat + ";" +
                 rider.dest_lng + "," + rider.dest_lat + ";" +
                 d.dest_lng + "," + d.dest_lat;
    var url = OSRM_URL + coords + "?overview=false";

    fetch(url)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.code === "Ok" && data.routes && data.routes.length) {
          var detourDuration = Math.round(data.routes[0].duration);
          var directDuration = d.route_duration || 0;
          var extraSeconds = detourDuration - directDuration;
          var extraMin = Math.max(1, Math.round(extraSeconds / 60));

          // Update the badge in the card
          var badge = item.card.querySelector(".detour-badge");
          if (badge) {
            badge.textContent = "+" + extraMin + " min detour";
            badge.classList.remove("detour-loading");
          }
        }
      })
      .catch(function () { /* leave estimate as-is */ });

    // Schedule next
    setTimeout(function () {
      processQueue(queue, rider, index + 1);
    }, THROTTLE_MS);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
