"""
Pure-Python routing utilities for along-the-way matching.

No external dependencies — implements Google polyline decoding and
great-circle distance calculations directly.
"""
import math

# ── Polyline decoding ────────────────────────────────────────


def decode_polyline(encoded):
    """
    Decode a Google-format encoded polyline string into a list of
    (latitude, longitude) tuples.

    Reference: https://developers.google.com/maps/documentation/utilities/polylinealgorithm
    """
    points = []
    index = 0
    lat = 0
    lng = 0
    length = len(encoded)

    while index < length:
        # Decode latitude
        shift = 0
        result = 0
        while True:
            b = ord(encoded[index]) - 63
            index += 1
            result |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        dlat = ~(result >> 1) if (result & 1) else (result >> 1)
        lat += dlat

        # Decode longitude
        shift = 0
        result = 0
        while True:
            b = ord(encoded[index]) - 63
            index += 1
            result |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        dlng = ~(result >> 1) if (result & 1) else (result >> 1)
        lng += dlng

        points.append((lat / 1e5, lng / 1e5))

    return points


# ── Distance helpers ─────────────────────────────────────────


_EARTH_RADIUS_MILES = 3958.8


def _haversine(lat1, lng1, lat2, lng2):
    """Great-circle distance in miles between two points."""
    rlat1 = math.radians(lat1)
    rlat2 = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(rlat1) * math.cos(rlat2) * math.sin(dlng / 2) ** 2)
    return _EARTH_RADIUS_MILES * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _point_to_segment_distance(plat, plng, alat, alng, blat, blng):
    """
    Approximate minimum distance in miles from point P to segment A-B.

    Projects P onto the line through A-B, clamps to the segment, and
    returns the haversine distance to the closest point.
    """
    dx = blat - alat
    dy = blng - alng
    seg_len_sq = dx * dx + dy * dy
    if seg_len_sq < 1e-12:
        return _haversine(plat, plng, alat, alng)

    t = ((plat - alat) * dx + (plng - alng) * dy) / seg_len_sq
    t = max(0.0, min(1.0, t))
    proj_lat = alat + t * dx
    proj_lng = alng + t * dy
    return _haversine(plat, plng, proj_lat, proj_lng)


# ── Public API ───────────────────────────────────────────────


def point_to_polyline_distance(lat, lng, polyline_points):
    """
    Find the minimum distance (miles) from a point to any segment of a
    decoded polyline.

    Returns (distance_miles, segment_index) where segment_index is the
    index of the closest segment's starting point.
    """
    best_dist = float("inf")
    best_idx = 0

    for i in range(len(polyline_points) - 1):
        alat, alng = polyline_points[i]
        blat, blng = polyline_points[i + 1]
        d = _point_to_segment_distance(lat, lng, alat, alng, blat, blng)
        if d < best_dist:
            best_dist = d
            best_idx = i

    return best_dist, best_idx


def is_along_route(
    pickup_lat, pickup_lng,
    dropoff_lat, dropoff_lng,
    polyline_points,
    max_proximity_miles=2.0,
):
    """
    Check whether a rider's pickup and dropoff are both near the
    driver's route and in the correct order (pickup before dropoff).

    Returns a dict:
        {
            "match": bool,
            "pickup_dist": float,     # miles from route to pickup
            "dropoff_dist": float,    # miles from route to dropoff
            "pickup_idx": int,        # segment index on route
            "dropoff_idx": int,       # segment index on route
            "est_detour_miles": float # rough extra distance
        }
    """
    pickup_dist, pickup_idx = point_to_polyline_distance(
        pickup_lat, pickup_lng, polyline_points
    )
    dropoff_dist, dropoff_idx = point_to_polyline_distance(
        dropoff_lat, dropoff_lng, polyline_points
    )

    match = (
        pickup_dist <= max_proximity_miles
        and dropoff_dist <= max_proximity_miles
        and pickup_idx <= dropoff_idx  # pickup comes before dropoff
    )

    return {
        "match": match,
        "pickup_dist": round(pickup_dist, 2),
        "dropoff_dist": round(dropoff_dist, 2),
        "pickup_idx": pickup_idx,
        "dropoff_idx": dropoff_idx,
        "est_detour_miles": round(pickup_dist + dropoff_dist, 2),
    }
