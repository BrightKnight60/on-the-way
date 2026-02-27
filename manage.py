#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def convert_legacy_persons():
    """
    Convert rides.Person records (legacy fixture format) into modern
    Ride entries so they appear on the platform.

    - Each Person with taking_passengers=True becomes an OPEN Ride
      driven by an auto-created User named after the person.
    - Each Person with taking_passengers=False becomes a rider with a
      pending RideRequest on the closest matching Ride (same destination).
    - Idempotent: skips records that have already been converted.
    """
    import django
    django.setup()

    from datetime import datetime

    from django.contrib.auth import get_user_model
    from django.utils import timezone

    from rides.models import Person, Profile, Ride, RideRequest

    User = get_user_model()
    persons = Person.objects.all()
    if not persons.exists():
        return

    print(f"\n  Converting {persons.count()} legacy Person record(s) to Rides...\n")

    created_rides = 0
    created_requests = 0
    skipped = 0

    for person in persons:
        # Build a stable email / username from the person's name + pk
        email = f"{person.first_name.lower()}.legacy{person.pk}@ontheway.local"

        # Get or create a User for this person
        user, u_created = User.objects.get_or_create(
            username=email,
            defaults={
                "email": email,
                "first_name": person.first_name,
            },
        )
        if u_created:
            user.set_password("demo1234")
            user.save()
            # Create profile
            Profile.objects.get_or_create(user=user)

        # Combine date + time into a timezone-aware datetime
        naive_dt = datetime.combine(person.date, person.time)
        departure = timezone.make_aware(naive_dt, timezone.utc)

        # Build origin and destination strings
        # If the origination already includes a state/zip (has a comma or digits),
        # use it as-is; otherwise assume NJ for the legacy data format.
        raw_orig = person.origination.strip()
        if "," in raw_orig or any(c.isdigit() for c in raw_orig):
            origin = raw_orig
        else:
            origin = f"{raw_orig}, NJ"
        destination = f"{person.destination_city}, {person.destination_state}"

        if person.taking_passengers and person.seats_available > 0:
            # This person is a driver offering seats -> create a Ride
            _, r_created = Ride.objects.get_or_create(
                driver=user,
                origin=origin,
                destination=destination,
                departure_time=departure,
                defaults={
                    "destination_state": person.destination_state,
                    "total_seats": person.seats_available,
                    "status": Ride.Status.OPEN,
                },
            )
            if r_created:
                created_rides += 1
                print(f"    + Ride: {person.first_name} — {origin} -> {destination} "
                      f"({person.seats_available} seats)")
            else:
                skipped += 1
        else:
            # This person is a rider -> find a matching open ride and request a seat
            # Skip if they already have a request to a ride with the same destination
            already_requested = RideRequest.objects.filter(
                rider=user,
                ride__destination__icontains=person.destination_city,
            ).exists()

            if already_requested:
                skipped += 1
                continue

            matching_ride = (
                Ride.objects.filter(
                    destination__icontains=person.destination_city,
                    status=Ride.Status.OPEN,
                )
                .exclude(driver=user)
                .order_by("departure_time")
                .first()
            )
            if matching_ride:
                _, rr_created = RideRequest.objects.get_or_create(
                    ride=matching_ride,
                    rider=user,
                    defaults={
                        "seats_requested": 1,
                        "status": RideRequest.Status.PENDING,
                    },
                )
                if rr_created:
                    created_requests += 1
                    print(f"    + Request: {person.first_name} requested seat on "
                          f"{matching_ride.driver.first_name}'s ride to {destination}")
                else:
                    skipped += 1
            else:
                # No matching ride found — create a ride for them anyway
                _, r_created = Ride.objects.get_or_create(
                    driver=user,
                    origin=origin,
                    destination=destination,
                    departure_time=departure,
                    defaults={
                        "destination_state": person.destination_state,
                        "total_seats": 1,
                        "status": Ride.Status.OPEN,
                    },
                )
                if r_created:
                    created_rides += 1
                    print(f"    + Ride (solo): {person.first_name} — {origin} -> {destination}")
                else:
                    skipped += 1

    print(f"\n  Done: {created_rides} ride(s), {created_requests} request(s) created"
          f" ({skipped} already existed).\n")


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'HandyRides.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc

    execute_from_command_line(sys.argv)

    # After loaddata finishes, convert any legacy Person records into Rides
    if len(sys.argv) >= 2 and sys.argv[1] == "loaddata":
        convert_legacy_persons()


if __name__ == '__main__':
    main()
