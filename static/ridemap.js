/**
 * ridemap.js — Leaflet map for ride search results and ride detail pages.
 *
 * Looks for <div class="ride-map" data-rides="[...]"> elements.
 * Each ride in the JSON array should have:
 *   { origin_lat, origin_lng, dest_lat, dest_lng, driver, origin,
 *     destination, color, polyline? }
 *
 * When a ride includes a `polyline` field (OSRM-encoded), it draws the
 * actual driving route. Otherwise falls back to a straight line.
 */
(function () {
  "use strict";

  /* ── Polyline decoder (Google format) ─────────────────────── */

  function decodePolyline(encoded) {
    var points = [];
    var index = 0, lat = 0, lng = 0, len = encoded.length;
    while (index < len) {
      var shift = 0, result = 0, b;
      do { b = encoded.charCodeAt(index++) - 63; result |= (b & 0x1f) << shift; shift += 5; } while (b >= 0x20);
      lat += (result & 1) ? ~(result >> 1) : (result >> 1);
      shift = 0; result = 0;
      do { b = encoded.charCodeAt(index++) - 63; result |= (b & 0x1f) << shift; shift += 5; } while (b >= 0x20);
      lng += (result & 1) ? ~(result >> 1) : (result >> 1);
      points.push([lat / 1e5, lng / 1e5]);
    }
    return points;
  }

  /* ── Init ─────────────────────────────────────────────────── */

  function init() {
    var containers = document.querySelectorAll(".ride-map");
    for (var i = 0; i < containers.length; i++) {
      initMap(containers[i]);
    }
  }

  function initMap(container) {
    var raw = container.getAttribute("data-rides");
    if (!raw) return;

    var rides;
    try { rides = JSON.parse(raw); } catch (e) { return; }

    var valid = rides.filter(function (r) {
      return r.origin_lat && r.origin_lng && r.dest_lat && r.dest_lng;
    });

    if (!valid.length) {
      container.style.display = "none";
      return;
    }

    var map = L.map(container, { scrollWheelZoom: false }).fitWorld();

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap contributors",
      maxZoom: 18
    }).addTo(map);

    var bounds = L.latLngBounds();

    valid.forEach(function (ride) {
      var color = ride.color || "#4f46e5";
      var originLL = L.latLng(ride.origin_lat, ride.origin_lng);
      var destLL   = L.latLng(ride.dest_lat, ride.dest_lng);

      bounds.extend(originLL);
      bounds.extend(destLL);

      // Draw route: actual polyline if available, else straight line
      var lineCoords;
      if (ride.polyline) {
        try {
          var decoded = decodePolyline(ride.polyline);
          lineCoords = decoded.map(function (p) { return L.latLng(p[0], p[1]); });
          // Extend bounds with full route
          for (var i = 0; i < lineCoords.length; i++) {
            bounds.extend(lineCoords[i]);
          }
        } catch (e) {
          lineCoords = [originLL, destLL];
        }
      } else {
        lineCoords = [originLL, destLL];
      }

      var line = L.polyline(lineCoords, {
        color: color, weight: 4, opacity: 0.8
      }).addTo(map);

      // Popup on line
      var popupHtml =
        "<strong>" + (ride.driver || "Driver") + "</strong><br>" +
        (ride.origin || "") + "<br>&darr;<br>" +
        (ride.destination || "");
      if (ride.price) popupHtml += "<br><em>" + ride.price + "</em>";
      if (ride.detour_min) popupHtml += "<br><em>+" + ride.detour_min + " min detour</em>";
      line.bindPopup(popupHtml);

      // Origin marker (circle)
      L.circleMarker(originLL, {
        radius: 6, color: color, fillColor: "#fff",
        fillOpacity: 1, weight: 2
      }).addTo(map).bindPopup("<b>Pickup:</b> " + (ride.origin || ""));

      // Destination marker (filled)
      L.circleMarker(destLL, {
        radius: 6, color: color, fillColor: color,
        fillOpacity: 1, weight: 2
      }).addTo(map).bindPopup("<b>Destination:</b> " + (ride.destination || ""));
    });

    map.fitBounds(bounds, { padding: [30, 30], maxZoom: 13 });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
