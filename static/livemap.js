/**
 * livemap.js — Live route preview for ride create / edit forms.
 *
 * Looks for a <div class="live-map"
 *   data-origin-input="<id>"
 *   data-dest-input="<id>">
 * element.
 *
 * Listens for "address-selected" events (fired by autocomplete.js)
 * on the origin and destination inputs, then fetches the actual
 * driving route from OSRM and draws it on the Leaflet map.
 *
 * Stores the encoded polyline and duration in hidden form fields
 * (id_route_polyline, id_route_duration) so they are saved with the ride.
 */
(function () {
  "use strict";

  var OSRM_URL = "https://router.project-osrm.org/route/v1/driving/";
  var DEFAULT_CENTER = [40.3487, -74.6593]; // Princeton
  var DEFAULT_ZOOM = 10;

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
    var containers = document.querySelectorAll(".live-map");
    for (var i = 0; i < containers.length; i++) {
      initLiveMap(containers[i]);
    }
  }

  function initLiveMap(container) {
    var originInputId = container.getAttribute("data-origin-input");
    var destInputId = container.getAttribute("data-dest-input");
    if (!originInputId || !destInputId) return;

    var originInput = document.getElementById(originInputId);
    var destInput = document.getElementById(destInputId);
    if (!originInput || !destInput) return;

    // Hidden fields for route data
    var polylineField = document.getElementById("id_route_polyline");
    var durationField = document.getElementById("id_route_duration");

    // State
    var state = { origin: null, dest: null, routeLatLngs: null };

    // Initialise the Leaflet map
    var map = L.map(container, { scrollWheelZoom: false })
      .setView(DEFAULT_CENTER, DEFAULT_ZOOM);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap contributors",
      maxZoom: 18
    }).addTo(map);

    // Layers we'll update
    var originMarker = null;
    var destMarker = null;
    var routeLine = null;

    // Check for pre-existing lat/lng (editing an existing ride)
    var originLatInput = document.getElementById(originInput.getAttribute("data-lat-target"));
    var originLngInput = document.getElementById(originInput.getAttribute("data-lng-target"));
    var destLatInput = document.getElementById(destInput.getAttribute("data-lat-target"));
    var destLngInput = document.getElementById(destInput.getAttribute("data-lng-target"));

    if (originLatInput && originLngInput && originLatInput.value && originLngInput.value) {
      state.origin = {
        lat: parseFloat(originLatInput.value),
        lng: parseFloat(originLngInput.value),
        name: originInput.value
      };
    }
    if (destLatInput && destLngInput && destLatInput.value && destLngInput.value) {
      state.dest = {
        lat: parseFloat(destLatInput.value),
        lng: parseFloat(destLngInput.value),
        name: destInput.value
      };
    }

    // If editing an existing ride with a stored polyline, decode it
    if (polylineField && polylineField.value) {
      try {
        state.routeLatLngs = decodePolyline(polylineField.value);
      } catch (e) { /* ignore bad polyline */ }
    }

    // Initial draw if editing existing ride
    if (state.origin || state.dest) {
      redraw();
    }

    // Listen for address selections
    originInput.addEventListener("address-selected", function (e) {
      state.origin = { lat: e.detail.lat, lng: e.detail.lng, name: e.detail.display_name };
      fetchRoute();
    });

    destInput.addEventListener("address-selected", function (e) {
      state.dest = { lat: e.detail.lat, lng: e.detail.lng, name: e.detail.display_name };
      fetchRoute();
    });

    function fetchRoute() {
      if (!state.origin || !state.dest) {
        state.routeLatLngs = null;
        redraw();
        return;
      }

      var coords = state.origin.lng + "," + state.origin.lat + ";" +
                   state.dest.lng + "," + state.dest.lat;
      var url = OSRM_URL + coords + "?overview=full&geometries=polyline";

      fetch(url)
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data.code === "Ok" && data.routes && data.routes.length) {
            var route = data.routes[0];

            // Store polyline and duration in hidden fields
            if (polylineField) polylineField.value = route.geometry;
            if (durationField) durationField.value = Math.round(route.duration);

            // Decode for map display
            state.routeLatLngs = decodePolyline(route.geometry);
          } else {
            state.routeLatLngs = null;
          }
          redraw();
        })
        .catch(function (err) {
          console.warn("OSRM route fetch error:", err);
          state.routeLatLngs = null;
          redraw();
        });
    }

    function redraw() {
      // Remove old layers
      if (originMarker) { map.removeLayer(originMarker); originMarker = null; }
      if (destMarker) { map.removeLayer(destMarker); destMarker = null; }
      if (routeLine) { map.removeLayer(routeLine); routeLine = null; }

      var bounds = L.latLngBounds();
      var hasPoints = false;

      if (state.origin) {
        var oLL = L.latLng(state.origin.lat, state.origin.lng);
        originMarker = L.circleMarker(oLL, {
          radius: 8, color: "#4f46e5", fillColor: "#fff",
          fillOpacity: 1, weight: 3
        }).addTo(map).bindPopup("<b>Pickup:</b> " + (state.origin.name || ""));
        bounds.extend(oLL);
        hasPoints = true;
      }

      if (state.dest) {
        var dLL = L.latLng(state.dest.lat, state.dest.lng);
        destMarker = L.circleMarker(dLL, {
          radius: 8, color: "#4f46e5", fillColor: "#4f46e5",
          fillOpacity: 1, weight: 3
        }).addTo(map).bindPopup("<b>Destination:</b> " + (state.dest.name || ""));
        bounds.extend(dLL);
        hasPoints = true;
      }

      // Draw actual OSRM route if available, else straight line
      if (state.origin && state.dest) {
        var lineCoords;
        if (state.routeLatLngs && state.routeLatLngs.length > 1) {
          lineCoords = state.routeLatLngs;
          // Extend bounds with full route
          for (var i = 0; i < lineCoords.length; i++) {
            bounds.extend(L.latLng(lineCoords[i][0], lineCoords[i][1]));
          }
        } else {
          lineCoords = [
            [state.origin.lat, state.origin.lng],
            [state.dest.lat, state.dest.lng]
          ];
        }
        routeLine = L.polyline(lineCoords, {
          color: "#4f46e5", weight: 4, opacity: 0.8
        }).addTo(map);
      }

      if (hasPoints) {
        if (state.origin && state.dest) {
          map.fitBounds(bounds, { padding: [40, 40], maxZoom: 13 });
        } else {
          map.setView(bounds.getCenter(), 12);
        }
      }
    }
  }

  // Export decoder for other scripts
  window.decodePolyline = decodePolyline;

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
