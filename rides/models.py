from django.conf import settings
from django.db import models


class Person(models.Model):
    """
    Legacy model representing a single person / trip entry.
    Kept for backwards-compatibility with existing data and migrations.
    """

    first_name = models.CharField(max_length=64)
    origination = models.CharField(max_length=64)
    destination_city = models.CharField(max_length=64)
    destination_state = models.CharField(max_length=2)
    date = models.DateField()
    time = models.TimeField()
    taking_passengers = models.BooleanField(default=False)
    seats_available = models.IntegerField(default=0)

    def __str__(self) -> str:
        return f"{self.first_name} from {self.origination} to {self.destination_city}, {self.destination_state}"


class Ride(models.Model):
    """
    A ride offered by a driver who is already going to a destination.
    Other users can request seats on this ride.
    """

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        FULL = "full", "Full"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    driver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="driven_rides",
    )
    origin = models.CharField(max_length=256)
    destination = models.CharField(max_length=256)
    destination_state = models.CharField(max_length=2, blank=True, default="")
    departure_time = models.DateTimeField()
    arrival_time_estimate = models.DateTimeField(blank=True, null=True)

    origin_lat = models.FloatField(blank=True, null=True)
    origin_lng = models.FloatField(blank=True, null=True)
    dest_lat = models.FloatField(blank=True, null=True)
    dest_lng = models.FloatField(blank=True, null=True)

    # OSRM route data (populated by JavaScript on ride create/edit)
    route_polyline = models.TextField(blank=True, default="")
    route_duration = models.IntegerField(blank=True, null=True)  # seconds
    max_detour_minutes = models.IntegerField(default=5)

    total_seats = models.PositiveSmallIntegerField()
    price_per_seat = models.DecimalField(
        max_digits=6, decimal_places=2, blank=True, null=True
    )
    notes = models.TextField(blank=True)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.OPEN
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Ride by {self.driver} from {self.origin} to {self.destination} at {self.departure_time}"


AVATAR_COLORS = [
    "#4f46e5", "#dc2626", "#16a34a", "#ea580c", "#0891b2",
    "#7c3aed", "#ca8a04", "#db2777", "#059669", "#0d9488",
]


class Profile(models.Model):
    """
    Extended user profile: bio blurb and avatar colour.
    Created automatically via get_or_create whenever needed.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    bio = models.TextField(blank=True, default="")
    avatar_color = models.CharField(max_length=7, blank=True, default="")

    def save(self, *args, **kwargs):
        if not self.avatar_color:
            self.avatar_color = AVATAR_COLORS[self.user_id % len(AVATAR_COLORS)]
        super().save(*args, **kwargs)

    @property
    def initial(self):
        name = self.user.first_name or self.user.username
        return name[0].upper() if name else "?"

    def __str__(self):
        return f"Profile for {self.user}"


class FavoriteLocation(models.Model):
    """
    A saved location (Home, Work, or custom) for quick search autofill.
    Each user can have up to 4: Home, Work, and 2 custom slots.
    """

    SLOT_CHOICES = [
        ("home", "Home"),
        ("work", "Work"),
        ("custom", "Custom"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="favorite_locations",
    )
    slot = models.CharField(max_length=8, choices=SLOT_CHOICES)
    label = models.CharField(max_length=64, blank=True)
    address = models.CharField(max_length=256, blank=True, default="")
    lat = models.FloatField(blank=True, null=True)
    lng = models.FloatField(blank=True, null=True)

    class Meta:
        ordering = ["pk"]

    def __str__(self):
        name = self.label or self.get_slot_display()
        return f"{name}: {self.address or '(empty)'}"


class RideRequest(models.Model):
    """
    A request from a rider to join a specific ride for one or more seats.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"

    ride = models.ForeignKey(
        Ride,
        on_delete=models.CASCADE,
        related_name="requests",
    )
    rider = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ride_requests",
    )
    seats_requested = models.PositiveSmallIntegerField(default=1)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.PENDING
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("ride", "rider")

    def __str__(self) -> str:
        return f"{self.rider} requests {self.seats_requested} seat(s) on {self.ride}"


class Rating(models.Model):
    """Rating of ride smoothness. Driver rates riders; rider rates driver."""

    ride = models.ForeignKey(Ride, on_delete=models.CASCADE, related_name="ratings")
    ride_request = models.ForeignKey(
        RideRequest,
        on_delete=models.CASCADE,
        related_name="ratings",
        help_text="Links rater/ratee for this ride (driver-rider pair)",
    )
    rater = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ratings_given",
    )
    ratee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ratings_received",
    )
    stars = models.PositiveSmallIntegerField(null=True, blank=True)  # 1-5, null when did_not_show_up
    did_not_show_up = models.BooleanField(default=False)  # driver only: rider did not show
    comment = models.TextField(blank=True)  # required when stars=1
    flagged = models.BooleanField(default=False)  # True when stars=1 or did_not_show_up

    class Meta:
        unique_together = ("rater", "ride_request")

    def __str__(self) -> str:
        if self.did_not_show_up:
            return f"{self.rater} rated {self.ratee}: did not show up"
        return f"{self.rater} rated {self.ratee}: {self.stars} stars"
