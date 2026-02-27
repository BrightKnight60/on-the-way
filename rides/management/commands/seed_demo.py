"""
Management command: python manage.py seed_demo

Creates demo users, rides, and ride-requests so the platform can be
fully demonstrated without manual data entry.

All demo users have password: demo1234
"""

import json
import time
import urllib.request
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from rides.models import Profile, Ride, RideRequest

User = get_user_model()

DEMO_PASSWORD = "demo1234"

USERS = [
    {
        "email": "alain@princeton.edu",
        "first_name": "Alain",
        "last_name": "Kornhauser",
        "bio": "Professor of Operations Research and Financial Engineering at Princeton University. Passionate about autonomous vehicles, transportation systems, and getting people where they need to go.",
    },
    {
        "email": "alice@example.com",
        "first_name": "Alice",
        "last_name": "Wang",
        "bio": "Junior at Princeton studying CS. I drive to NYC and EWR pretty often - happy to give rides! Love chatting about tech and music on road trips.",
    },
    {
        "email": "bob@example.com",
        "first_name": "Bob",
        "last_name": "Smith",
        "bio": "Grad student in Mechanical Engineering. I have a Honda CR-V with plenty of trunk space. Usually drive to Philly on weekends.",
    },
    {
        "email": "charlie@example.com",
        "first_name": "Charlie",
        "last_name": "Lee",
        "bio": "Sophomore, econ major. I run errands around Princeton and take road trips whenever I can. Always down to split gas costs!",
    },
    {
        "email": "diana@example.com",
        "first_name": "Diana",
        "last_name": "Patel",
        "bio": "Pre-med senior. I don't have a car, so I'm usually looking for rides. Quiet passenger, happy to help with gas money.",
    },
    {
        "email": "eric@example.com",
        "first_name": "Eric",
        "last_name": "Johnson",
        "bio": "MBA '26. I drive a comfortable sedan and frequently go shopping on Route 1. Also going to DC for spring break - riders welcome!",
    },
]

# (driver email, origin, destination, state, hours_from_now, seats, price, notes,
#  origin_lat, origin_lng, dest_lat, dest_lng, max_detour_minutes)
RIDES = [
    (
        "alice@example.com",
        "Frist Campus Center, Princeton, NJ",
        "Newark Liberty International Airport (EWR)",
        "NJ", 6, 3, 15.00,
        "Leaving from Frist. Can fit luggage in trunk.",
        40.3467, -74.6551, 40.6895, -74.1745, 10,
    ),
    (
        "alice@example.com",
        "Princeton University",
        "Penn Station, New York, NY",
        "NY", 28, 2, 20.00,
        "Taking Route 1 to NJ Transit or driving all the way if enough riders.",
        40.3431, -74.6551, 40.7506, -73.9935, 8,
    ),
    (
        "bob@example.com",
        "Engineering Quad, Princeton, NJ",
        "Philadelphia International Airport (PHL)",
        "PA", 10, 4, 18.00,
        "Happy to stop at 30th Street Station on the way.",
        40.3505, -74.6520, 39.8744, -75.2424, 15,
    ),
    (
        "bob@example.com",
        "Nassau Hall, Princeton, NJ",
        "Princeton Junction NJ Transit Station",
        "NJ", 3, 2, None,
        "Quick trip to the train station. Free ride!",
        40.3487, -74.6593, 40.3163, -74.6238, 3,
    ),
    (
        "charlie@example.com",
        "Witherspoon St, Princeton, NJ",
        "Target, 500 Nassau Park Blvd, Princeton, NJ",
        "NJ", 2, 3, None,
        "Running errands, happy to bring people along.",
        40.3521, -74.6629, 40.3272, -74.6821, 5,
    ),
    (
        "charlie@example.com",
        "Princeton, NJ",
        "Boston, MA",
        "MA", 48, 3, 40.00,
        "Road trip to Boston for the weekend. Splitting gas.",
        40.3487, -74.6593, 42.3601, -71.0589, 15,
    ),
    (
        "diana@example.com",
        "Princeton, NJ",
        "Washington, DC",
        "DC", 72, 3, 35.00,
        "Driving down for spring break. Leaving early morning.",
        40.3487, -74.6593, 38.9072, -77.0369, 12,
    ),
    (
        "eric@example.com",
        "Wawa, 152 Alexander St, Princeton, NJ",
        "Nordstrom Rack, 3371 US Highway 1, Lawrenceville, NJ",
        "NJ", 5, 2, 5.00,
        "Quick shopping trip on Route 1.",
        40.3494, -74.6572, 40.3025, -74.6920, 5,
    ),
]

# (rider email, ride index, seats)
REQUESTS = [
    ("diana@example.com", 0, 1),   # Diana requests Alice's EWR ride
    ("eric@example.com",  0, 2),   # Eric requests Alice's EWR ride
    ("charlie@example.com", 1, 1), # Charlie requests Alice's NYC ride
    ("alice@example.com", 2, 1),   # Alice requests Bob's PHL ride
    ("diana@example.com", 5, 2),   # Diana requests Charlie's Boston ride
]


def _fetch_osrm_route(olng, olat, dlng, dlat):
    """
    Fetch the driving route from the public OSRM demo server.
    Returns (polyline, duration_seconds) or (None, None) on error.
    """
    url = (
        f"https://router.project-osrm.org/route/v1/driving/"
        f"{olng},{olat};{dlng},{dlat}?overview=full&geometries=polyline"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "OnTheWay-Seed/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        if data.get("code") == "Ok" and data.get("routes"):
            route = data["routes"][0]
            return route["geometry"], round(route["duration"])
    except Exception:
        pass
    return None, None


class Command(BaseCommand):
    help = "Seed the database with demo users, rides, and ride requests."

    def handle(self, *args, **options):
        now = timezone.now()

        # ── Users ──
        user_map = {}
        for u in USERS:
            user, created = User.objects.get_or_create(
                username=u["email"],
                defaults={
                    "email": u["email"],
                    "first_name": u["first_name"],
                    "last_name": u["last_name"],
                },
            )
            if created:
                user.set_password(DEMO_PASSWORD)
                user.save()
                self.stdout.write(self.style.SUCCESS(f"  Created user {u['email']}"))
            else:
                self.stdout.write(f"  User {u['email']} already exists, skipping.")
            user_map[u["email"]] = user

            # Create / update profile with bio
            profile, p_created = Profile.objects.get_or_create(user=user)
            if u.get("bio") and not profile.bio:
                profile.bio = u["bio"]
                profile.save()
                if p_created:
                    self.stdout.write(self.style.SUCCESS(f"  Created profile for {u['email']}"))

        # ── Rides ──
        ride_objs = []
        for (driver_email, origin, dest, state, hours, seats, price, notes,
             olat, olng, dlat, dlng, max_detour) in RIDES:
            ride, created = Ride.objects.get_or_create(
                driver=user_map[driver_email],
                origin=origin,
                destination=dest,
                defaults={
                    "destination_state": state,
                    "departure_time": now + timedelta(hours=hours),
                    "total_seats": seats,
                    "price_per_seat": price,
                    "notes": notes,
                    "status": Ride.Status.OPEN,
                    "origin_lat": olat,
                    "origin_lng": olng,
                    "dest_lat": dlat,
                    "dest_lng": dlng,
                    "max_detour_minutes": max_detour,
                },
            )
            ride_objs.append(ride)
            if created:
                self.stdout.write(self.style.SUCCESS(f"  Created ride: {origin} -> {dest}"))
            else:
                self.stdout.write(f"  Ride {origin} -> {dest} already exists, skipping.")

        # ── Fetch OSRM routes for rides that don't have one yet ──
        self.stdout.write("\nFetching driving routes from OSRM...")
        for ride in ride_objs:
            if ride.route_polyline:
                self.stdout.write(f"  Route already stored for: {ride.origin} -> {ride.destination}")
                continue
            if not (ride.origin_lat and ride.origin_lng and ride.dest_lat and ride.dest_lng):
                continue
            polyline, duration = _fetch_osrm_route(
                ride.origin_lng, ride.origin_lat,
                ride.dest_lng, ride.dest_lat,
            )
            if polyline:
                ride.route_polyline = polyline
                ride.route_duration = duration
                ride.save(update_fields=["route_polyline", "route_duration"])
                self.stdout.write(self.style.SUCCESS(
                    f"  Route stored for: {ride.origin} -> {ride.destination} "
                    f"({duration}s, {len(polyline)} chars)"
                ))
            else:
                self.stdout.write(self.style.WARNING(
                    f"  Could not fetch route for: {ride.origin} -> {ride.destination}"
                ))
            time.sleep(1.1)  # Respect OSRM rate limit (~1 req/sec)

        # ── Ride requests ──
        for rider_email, ride_idx, seats in REQUESTS:
            req, created = RideRequest.objects.get_or_create(
                ride=ride_objs[ride_idx],
                rider=user_map[rider_email],
                defaults={
                    "seats_requested": seats,
                    "status": RideRequest.Status.PENDING,
                },
            )
            if created:
                self.stdout.write(self.style.SUCCESS(
                    f"  {rider_email} requested {seats} seat(s) on ride #{ride_idx + 1}"
                ))

        self.stdout.write(self.style.SUCCESS("\nDemo data seeded successfully!"))
        self.stdout.write(f"\nAll demo accounts use password: {DEMO_PASSWORD}")
        self.stdout.write("Try signing in as alice@example.com or bob@example.com")
