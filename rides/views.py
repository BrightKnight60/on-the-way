import json
import logging

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.db.models import Avg, Q, Sum
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import ProfileForm, RatingForm, RideCreateForm, RideSearchForm, SignUpForm
from .models import FavoriteLocation, Profile, Rating, Ride, RideRequest

logger = logging.getLogger(__name__)


# ── Splash page ──────────────────────────────────────────────


def splash_or_home(request):
    """Show the splash page on a user's first visit, then redirect to /rides/ after."""
    if request.COOKIES.get("otw_visited"):
        return redirect("rides:rider_search")
    return render(request, "index.html")


def _get_or_create_profile(user):
    """Return the Profile for user, creating it if needed."""
    profile, _ = Profile.objects.get_or_create(user=user)
    return profile


def _get_driver_color(driver):
    """Return the avatar colour for a driver from their Profile."""
    from .models import AVATAR_COLORS
    try:
        return driver.profile.avatar_color or AVATAR_COLORS[driver.pk % len(AVATAR_COLORS)]
    except Exception:
        return AVATAR_COLORS[driver.pk % len(AVATAR_COLORS)]


def _ride_to_map_json(ride, color=None, detour_min=None):
    """Serialize a Ride into a dict suitable for ridemap.js."""
    data = {
        "origin_lat": ride.origin_lat,
        "origin_lng": ride.origin_lng,
        "dest_lat": ride.dest_lat,
        "dest_lng": ride.dest_lng,
        "driver": ride.driver.first_name or ride.driver.username,
        "origin": ride.origin,
        "destination": ride.destination,
        "price": f"${ride.price_per_seat}/seat" if ride.price_per_seat else "Free",
        "color": color or _get_driver_color(ride.driver),
    }
    # Include polyline so the map draws actual driving routes
    if ride.route_polyline:
        data["polyline"] = ride.route_polyline
    if detour_min is not None:
        data["detour_min"] = detour_min
    return data


# ── Driver views ─────────────────────────────────────────────


@login_required
def driver_dashboard(request):
    rides = Ride.objects.filter(driver=request.user).order_by("-departure_time")
    return render(request, "index_view.html", {"rides": rides})


@login_required
def create_ride(request):
    if request.method == "POST":
        form = RideCreateForm(request.POST)
        if form.is_valid():
            try:
                ride = form.save(commit=False)
                ride.driver = request.user
                ride.save()
                messages.success(request, "Your ride has been published!")
                return redirect("rides:ride_detail", pk=ride.pk)
            except Exception:
                logger.exception("Error creating ride")
                messages.error(request, "Something went wrong while creating your ride. Please try again.")
        else:
            messages.error(request, "Please fix the errors below.")
    else:
        form = RideCreateForm()

    return render(request, "create_ride.html", {"form": form})


@login_required
def ride_detail(request, pk):
    try:
        ride = Ride.objects.select_related("driver", "driver__profile").get(pk=pk, driver=request.user)
    except Ride.DoesNotExist:
        messages.error(request, "That ride was not found or you don't have access to it.")
        return redirect("rides:index")

    ride_json = json.dumps([_ride_to_map_json(ride)])
    return render(
        request,
        "ride_detail.html",
        {"ride": ride, "ride_json": ride_json, "now": timezone.now()},
    )


@login_required
def edit_ride(request, pk):
    try:
        ride = Ride.objects.get(pk=pk, driver=request.user)
    except Ride.DoesNotExist:
        messages.error(request, "That ride was not found or you don't have access to it.")
        return redirect("rides:index")

    if request.method == "POST":
        form = RideCreateForm(request.POST, instance=ride)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, "Ride updated successfully.")
                return redirect("rides:ride_detail", pk=ride.pk)
            except Exception:
                logger.exception("Error updating ride")
                messages.error(request, "Something went wrong while saving your changes. Please try again.")
        else:
            messages.error(request, "Please fix the errors below.")
    else:
        form = RideCreateForm(instance=ride)

    return render(request, "edit_ride.html", {"form": form, "ride": ride})


@login_required
def delete_ride(request, pk):
    try:
        ride = Ride.objects.get(pk=pk, driver=request.user)
    except Ride.DoesNotExist:
        messages.error(request, "That ride was not found or you don't have access to it.")
        return redirect("rides:index")

    if request.method == "POST":
        try:
            ride.delete()
            messages.success(request, "Ride deleted.")
            return redirect("rides:index")
        except Exception:
            logger.exception("Error deleting ride")
            messages.error(request, "Something went wrong while deleting the ride. Please try again.")
            return redirect("rides:ride_detail", pk=ride.pk)

    return render(request, "confirm_delete_ride.html", {"ride": ride})


@login_required
@require_POST
def complete_ride(request, pk):
    """Mark a ride as completed (driver only, ride must be in the past)."""
    try:
        ride = Ride.objects.get(pk=pk, driver=request.user)
    except Ride.DoesNotExist:
        messages.error(request, "That ride was not found.")
        return redirect("rides:index")

    if ride.status not in (Ride.Status.OPEN, Ride.Status.FULL):
        messages.error(request, "That ride cannot be marked as completed.")
        return redirect("rides:ride_detail", pk=ride.pk)

    if ride.departure_time > timezone.now():
        messages.error(request, "You can only complete rides after their departure time.")
        return redirect("rides:ride_detail", pk=ride.pk)

    ride.status = Ride.Status.COMPLETED
    ride.save()
    messages.success(request, "Ride marked as completed.")
    return redirect("rides:ride_detail", pk=ride.pk)


# ── Rider views ─────────────────────────────────────────────


def _proximity_q(lat, lng, lat_field, lng_field, miles=1.0):
    """
    Return a Q object matching rows within *miles* of (lat, lng).
    Useful for OR-ing with text-based fallback queries.
    """
    import math
    dlat = miles / 69.0
    dlng = miles / (69.0 * math.cos(math.radians(lat)))
    return Q(**{
        f"{lat_field}__gte": lat - dlat,
        f"{lat_field}__lte": lat + dlat,
        f"{lng_field}__gte": lng - dlng,
        f"{lng_field}__lte": lng + dlng,
    })


def _proximity_filter(qs, lat, lng, lat_field, lng_field, miles=1.0):
    """
    Filter a queryset to rows within *miles* of (lat, lng).
    Uses a bounding-box approximation (fast, no PostGIS needed).
    1 mile ≈ 0.01449° lat; lng varies by latitude but ~0.019° at US mid-latitudes.
    """
    import math
    dlat = miles / 69.0                       # degrees latitude per mile
    dlng = miles / (69.0 * math.cos(math.radians(lat)))  # adjusted for latitude
    return qs.filter(**{
        f"{lat_field}__gte": lat - dlat,
        f"{lat_field}__lte": lat + dlat,
        f"{lng_field}__gte": lng - dlng,
        f"{lng_field}__lte": lng + dlng,
    })


@login_required
def rider_search(request):
    form = RideSearchForm(request.GET or None)
    rides = None
    searched = False
    # Maps ride.pk -> estimated detour minutes (for along-the-way matches)
    detour_map = {}

    if form.is_valid() and form.has_query():
        searched = True
        try:
            qs = Ride.objects.filter(status=Ride.Status.OPEN).select_related("driver", "driver__profile")

            origin = form.cleaned_data.get("origin", "").strip()
            destination = form.cleaned_data.get("destination", "").strip()
            state = form.cleaned_data.get("state", "").strip()
            origin_lat = form.cleaned_data.get("origin_lat")
            origin_lng = form.cleaned_data.get("origin_lng")
            dest_lat = form.cleaned_data.get("dest_lat")
            dest_lng = form.cleaned_data.get("dest_lng")

            # ── Pass 1: standard proximity / text matching ──
            # Use proximity when coords are available, but also OR-in
            # text matches so rides without coordinates are still found.
            direct_qs = qs

            if origin_lat and origin_lng:
                prox_q = _proximity_q(origin_lat, origin_lng, "origin_lat", "origin_lng")
                if origin:
                    direct_qs = direct_qs.filter(prox_q | Q(origin__icontains=origin))
                else:
                    direct_qs = direct_qs.filter(prox_q)
            elif origin:
                direct_qs = direct_qs.filter(origin__icontains=origin)

            if dest_lat and dest_lng:
                prox_q = _proximity_q(dest_lat, dest_lng, "dest_lat", "dest_lng")
                if destination:
                    direct_qs = direct_qs.filter(prox_q | Q(destination__icontains=destination))
                else:
                    direct_qs = direct_qs.filter(prox_q)
            elif destination:
                direct_qs = direct_qs.filter(destination__icontains=destination)

            if state:
                direct_qs = direct_qs.filter(destination_state__iexact=state)

            direct_rides = list(direct_qs.order_by("departure_time"))
            direct_pks = {r.pk for r in direct_rides}

            # ── Pass 2: along-the-way matching ──
            # Only if rider provided both pickup and dropoff coordinates
            along_rides = []
            if origin_lat and origin_lng and dest_lat and dest_lng:
                from .routing import decode_polyline, is_along_route

                # Candidates: open rides with a stored route polyline,
                # excluding rides already matched in pass 1
                candidates = (
                    qs.exclude(pk__in=direct_pks)
                    .exclude(route_polyline="")
                    .order_by("departure_time")
                )
                if state:
                    candidates = candidates.filter(destination_state__iexact=state)

                for ride in candidates:
                    try:
                        points = decode_polyline(ride.route_polyline)
                        if len(points) < 2:
                            continue
                        result = is_along_route(
                            origin_lat, origin_lng,
                            dest_lat, dest_lng,
                            points,
                            max_proximity_miles=2.0,
                        )
                        if not result["match"]:
                            continue

                        # Estimate detour in minutes (~30 mph average for detour)
                        est_minutes = round(result["est_detour_miles"] * 2)  # 2 min/mile detour
                        if est_minutes > ride.max_detour_minutes:
                            continue

                        detour_map[ride.pk] = est_minutes
                        along_rides.append(ride)
                    except Exception:
                        continue

            # Annotate all rides with est_detour (None for direct, int for along-the-way)
            for ride in direct_rides:
                ride.est_detour = None
            for ride in along_rides:
                ride.est_detour = detour_map.get(ride.pk)
            all_rides = direct_rides + along_rides
            rides = sorted(all_rides, key=lambda r: r.departure_time)

        except Exception:
            logger.exception("Error searching rides")
            messages.error(request, "Something went wrong with your search. Please try again.")

    rides_json = "[]"
    rider_coords = None
    if rides:
        map_data = [_ride_to_map_json(r, detour_min=detour_map.get(r.pk)) for r in rides]
        rides_json = json.dumps(map_data)

    # Pass rider coordinates to the template for async detour refinement
    if form.is_valid():
        origin_lat = form.cleaned_data.get("origin_lat")
        origin_lng = form.cleaned_data.get("origin_lng")
        dest_lat = form.cleaned_data.get("dest_lat")
        dest_lng = form.cleaned_data.get("dest_lng")
        if origin_lat and origin_lng and dest_lat and dest_lng:
            rider_coords = json.dumps({
                "lat": origin_lat, "lng": origin_lng,
                "dest_lat": dest_lat, "dest_lng": dest_lng,
            })

    # ── Favorites ──
    _ensure_default_favorites(request.user)
    favorites = list(FavoriteLocation.objects.filter(user=request.user))
    favorites_json = json.dumps([
        {
            "id": f.pk,
            "slot": f.slot,
            "label": f.label or f.get_slot_display(),
            "address": f.address,
            "lat": f.lat,
            "lng": f.lng,
        }
        for f in favorites
    ])

    # ── Recents (last 5 distinct origin/destination pairs) ──
    seen = set()
    recents = []
    # Rides the user requested seats on
    user_requests = (
        RideRequest.objects.filter(rider=request.user)
        .select_related("ride")
        .order_by("-created_at")
    )
    for rr in user_requests:
        r = rr.ride
        key = (r.origin, r.destination)
        if key not in seen:
            seen.add(key)
            recents.append({
                "origin": r.origin,
                "destination": r.destination,
                "origin_lat": r.origin_lat,
                "origin_lng": r.origin_lng,
                "dest_lat": r.dest_lat,
                "dest_lng": r.dest_lng,
            })
        if len(recents) >= 5:
            break
    # Also include rides the user drove
    if len(recents) < 5:
        user_rides = Ride.objects.filter(driver=request.user).order_by("-created_at")
        for r in user_rides:
            key = (r.origin, r.destination)
            if key not in seen:
                seen.add(key)
                recents.append({
                    "origin": r.origin,
                    "destination": r.destination,
                    "origin_lat": r.origin_lat,
                    "origin_lng": r.origin_lng,
                    "dest_lat": r.dest_lat,
                    "dest_lng": r.dest_lng,
                })
            if len(recents) >= 5:
                break
    recents_json = json.dumps(recents)

    context = {
        "form": form,
        "rides": rides,
        "searched": searched,
        "rides_json": rides_json,
        "detour_map": detour_map,
        "rider_coords": rider_coords,
        "favorites": favorites,
        "favorites_json": favorites_json,
        "recents": recents,
        "recents_json": recents_json,
    }
    return render(request, "rider_search.html", context)


@login_required
@require_POST
def request_ride(request, pk):
    try:
        ride = Ride.objects.select_related("driver").get(pk=pk, status=Ride.Status.OPEN)
    except Ride.DoesNotExist:
        messages.error(request, "This ride is no longer available.")
        return redirect("rides:rider_search")

    if ride.driver == request.user:
        messages.error(request, "You can't request a seat on your own ride.")
        return redirect("rides:rider_search")

    try:
        _, created = RideRequest.objects.get_or_create(
            ride=ride,
            rider=request.user,
            defaults={"seats_requested": 1, "status": RideRequest.Status.PENDING},
        )

        if created:
            messages.success(request, "Seat requested! The driver will review your request.")
        else:
            messages.info(request, "You've already requested a seat on this ride.")
    except IntegrityError:
        messages.info(request, "You've already requested a seat on this ride.")
    except Exception:
        logger.exception("Error requesting ride")
        messages.error(request, "Something went wrong. Please try again.")

    return redirect("rides:my_requests")


@login_required
def my_requests(request):
    requests_qs = (
        RideRequest.objects.filter(rider=request.user)
        .select_related("ride", "ride__driver")
        .order_by("-created_at")
    )
    return render(request, "my_requests.html", {"requests": requests_qs})


@login_required
def request_detail(request, req_pk):
    """Rider-facing view of a ride they have requested to join."""
    try:
        req = RideRequest.objects.select_related("ride", "ride__driver", "ride__driver__profile").get(
            pk=req_pk, rider=request.user
        )
    except RideRequest.DoesNotExist:
        messages.error(request, "That request was not found.")
        return redirect("rides:my_requests")

    ride = req.ride
    ride_json = json.dumps([_ride_to_map_json(ride)])
    return render(
        request,
        "request_detail.html",
        {"ride": ride, "req": req, "ride_json": ride_json},
    )


@login_required
@require_POST
def cancel_request(request, req_pk):
    """Cancel a pending ride request."""
    try:
        ride_req = RideRequest.objects.get(pk=req_pk, rider=request.user)
    except RideRequest.DoesNotExist:
        messages.error(request, "That request was not found.")
        return redirect("rides:my_requests")

    if ride_req.status != RideRequest.Status.PENDING:
        messages.error(request, "Only pending requests can be cancelled.")
        return redirect("rides:my_requests")

    ride_req.status = RideRequest.Status.CANCELLED
    ride_req.save()
    messages.success(request, "Your ride request has been cancelled.")
    return redirect("rides:my_requests")


@login_required
@require_POST
def accept_request(request, pk, req_pk):
    try:
        ride = Ride.objects.get(pk=pk, driver=request.user)
    except Ride.DoesNotExist:
        messages.error(request, "Ride not found.")
        return redirect("rides:index")

    try:
        ride_req = RideRequest.objects.select_related("rider").get(
            pk=req_pk, ride=ride, status=RideRequest.Status.PENDING
        )
    except RideRequest.DoesNotExist:
        messages.error(request, "This request is no longer pending.")
        return redirect("rides:ride_detail", pk=ride.pk)

    try:
        ride_req.status = RideRequest.Status.ACCEPTED
        ride_req.save()

        accepted_seats = (
            ride.requests.filter(status=RideRequest.Status.ACCEPTED)
            .aggregate(total=Sum("seats_requested"))["total"]
            or 0
        )
        if accepted_seats >= ride.total_seats:
            ride.status = Ride.Status.FULL
            ride.save()

        name = ride_req.rider.first_name or ride_req.rider.username
        messages.success(request, f"{name}'s request has been accepted.")
    except Exception:
        logger.exception("Error accepting request")
        messages.error(request, "Something went wrong. Please try again.")

    return redirect("rides:ride_detail", pk=ride.pk)


@login_required
@require_POST
def reject_request(request, pk, req_pk):
    try:
        ride = Ride.objects.get(pk=pk, driver=request.user)
    except Ride.DoesNotExist:
        messages.error(request, "Ride not found.")
        return redirect("rides:index")

    try:
        ride_req = RideRequest.objects.select_related("rider").get(
            pk=req_pk, ride=ride, status=RideRequest.Status.PENDING
        )
    except RideRequest.DoesNotExist:
        messages.error(request, "This request is no longer pending.")
        return redirect("rides:ride_detail", pk=ride.pk)

    try:
        ride_req.status = RideRequest.Status.REJECTED
        ride_req.save()
        name = ride_req.rider.first_name or ride_req.rider.username
        messages.info(request, f"{name}'s request has been declined.")
    except Exception:
        logger.exception("Error rejecting request")
        messages.error(request, "Something went wrong. Please try again.")

    return redirect("rides:ride_detail", pk=ride.pk)


# ── Ratings views ─────────────────────────────────────────────


@login_required
def ratings_page(request):
    """List rides the user can rate: as driver (rate riders) and as rider (rate driver)."""
    # Rides you drove: completed rides, user is driver, has accepted riders
    driven_rides = (
        Ride.objects.filter(
            driver=request.user,
            status=Ride.Status.COMPLETED,
        )
        .prefetch_related("requests")
        .order_by("-departure_time")
    )
    driver_rateable = []
    for ride in driven_rides:
        for req in ride.requests.filter(status=RideRequest.Status.ACCEPTED):
            driver_rateable.append({"ride": ride, "ride_request": req, "ratee": req.rider})

    # Rides you took: completed rides, user was accepted rider
    rider_reqs = (
        RideRequest.objects.filter(
            rider=request.user,
            status=RideRequest.Status.ACCEPTED,
            ride__status=Ride.Status.COMPLETED,
        )
        .select_related("ride", "ride__driver", "ride__driver__profile")
        .order_by("-ride__departure_time")
    )
    rider_rateable = [{"ride": rr.ride, "ride_request": rr, "ratee": rr.ride.driver} for rr in rider_reqs]

    # Existing ratings by (rater, ride_request)
    ratings_by_req = {
        (r.rater_id, r.ride_request_id): r
        for r in Rating.objects.filter(rater=request.user).select_related("ride_request")
    }

    driver_items = []
    for item in driver_rateable:
        req = item["ride_request"]
        rating = ratings_by_req.get((request.user.id, req.id))
        driver_items.append({**item, "rating": rating, "form": RatingForm(is_driver_rating=True)})

    rider_items = []
    for item in rider_rateable:
        req = item["ride_request"]
        rating = ratings_by_req.get((request.user.id, req.id))
        rider_items.append({**item, "rating": rating, "form": RatingForm(is_driver_rating=False)})

    context = {
        "driver_items": driver_items,
        "rider_items": rider_items,
    }
    return render(request, "ratings.html", context)


@login_required
@require_POST
def submit_rating(request):
    """Submit a rating for a ride (driver rates rider, or rider rates driver)."""
    ride_request_pk = request.POST.get("ride_request_pk")
    ratee_id = request.POST.get("ratee_id")
    stars_raw = request.POST.get("stars")
    did_not_show_up = request.POST.get("did_not_show_up") == "1"
    comment = (request.POST.get("comment") or "").strip()

    if not ride_request_pk or not ratee_id:
        messages.error(request, "Invalid rating submission.")
        return redirect("rides:ratings")

    try:
        ride_req = RideRequest.objects.select_related("ride", "rider").get(
            pk=ride_request_pk,
            status=RideRequest.Status.ACCEPTED,
            ride__status=Ride.Status.COMPLETED,
        )
    except RideRequest.DoesNotExist:
        messages.error(request, "That ride request was not found.")
        return redirect("rides:ratings")

    ride = ride_req.ride
    ratee_id = int(ratee_id)

    # Determine rater and validate ratee
    if ride.driver_id == request.user.id:
        # Driver rating rider
        if ride_req.rider_id != ratee_id:
            messages.error(request, "Invalid rating.")
            return redirect("rides:ratings")
        ratee = ride_req.rider
        is_driver_rating = True
    elif ride_req.rider_id == request.user.id:
        # Rider rating driver
        if ride.driver_id != ratee_id:
            messages.error(request, "Invalid rating.")
            return redirect("rides:ratings")
        ratee = ride.driver
        is_driver_rating = False
    else:
        messages.error(request, "You cannot rate this ride.")
        return redirect("rides:ratings")

    # Validate did_not_show_up (driver only)
    if did_not_show_up and not is_driver_rating:
        messages.error(request, "Only drivers can mark 'did not show up'.")
        return redirect("rides:ratings")

    # Check for existing rating
    if Rating.objects.filter(rater=request.user, ride_request=ride_req).exists():
        messages.error(request, "You have already rated this ride.")
        return redirect("rides:ratings")

    if did_not_show_up:
        Rating.objects.create(
            ride=ride,
            ride_request=ride_req,
            rater=request.user,
            ratee=ratee,
            stars=None,
            did_not_show_up=True,
            flagged=True,
        )
        messages.success(request, "Rating submitted.")
        return redirect("rides:ratings")

    # Require stars 1-5
    try:
        stars = int(stars_raw) if stars_raw else None
    except (ValueError, TypeError):
        stars = None
    if stars not in (1, 2, 3, 4, 5):
        messages.error(request, "Please select a rating from 1 to 5 stars.")
        return redirect("rides:ratings")

    if stars == 1 and not comment:
        messages.error(request, "A comment is required for severely disrupted rides.")
        return redirect("rides:ratings")

    Rating.objects.create(
        ride=ride,
        ride_request=ride_req,
        rater=request.user,
        ratee=ratee,
        stars=stars,
        did_not_show_up=False,
        comment=comment if stars == 1 else "",
        flagged=(stars == 1),
    )
    messages.success(request, "Rating submitted.")
    return redirect("rides:ratings")


# ── Profile views ─────────────────────────────────────────────


@login_required
def my_profile(request):
    profile = _get_or_create_profile(request.user)

    if request.method == "POST":
        form = ProfileForm(request.POST, instance=profile)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, "Profile updated.")
            except Exception:
                logger.exception("Error saving profile")
                messages.error(request, "Couldn't save your profile. Please try again.")
            return redirect("rides:my_profile")
        else:
            messages.error(request, "Please fix the errors below.")
    else:
        form = ProfileForm(instance=profile)

    rides_offered = Ride.objects.filter(driver=request.user).count()
    rides_taken = RideRequest.objects.filter(
        rider=request.user, status=RideRequest.Status.ACCEPTED
    ).count()

    rating_agg = Rating.objects.filter(
        ratee=request.user, did_not_show_up=False
    ).exclude(stars__isnull=True).aggregate(avg=Avg("stars"))
    avg_rating = rating_agg["avg"]
    rating_count = Rating.objects.filter(
        ratee=request.user, did_not_show_up=False
    ).exclude(stars__isnull=True).count()

    context = {
        "profile_user": request.user,
        "profile": profile,
        "form": form,
        "is_own": True,
        "rides_offered": rides_offered,
        "rides_taken": rides_taken,
        "avg_rating": round(avg_rating, 1) if avg_rating is not None else None,
        "rating_count": rating_count,
    }
    return render(request, "profile.html", context)


@login_required
def user_profile(request, user_id):
    from django.contrib.auth import get_user_model
    User = get_user_model()

    try:
        profile_user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        messages.error(request, "User not found.")
        return redirect("rides:index")

    if profile_user == request.user:
        return redirect("rides:my_profile")

    profile = _get_or_create_profile(profile_user)

    rides_offered = Ride.objects.filter(driver=profile_user).count()
    rides_taken = RideRequest.objects.filter(
        rider=profile_user, status=RideRequest.Status.ACCEPTED
    ).count()

    rating_agg = Rating.objects.filter(
        ratee=profile_user, did_not_show_up=False
    ).exclude(stars__isnull=True).aggregate(avg=Avg("stars"))
    avg_rating = rating_agg["avg"]
    rating_count = Rating.objects.filter(
        ratee=profile_user, did_not_show_up=False
    ).exclude(stars__isnull=True).count()

    context = {
        "profile_user": profile_user,
        "profile": profile,
        "is_own": False,
        "rides_offered": rides_offered,
        "rides_taken": rides_taken,
        "avg_rating": round(avg_rating, 1) if avg_rating is not None else None,
        "rating_count": rating_count,
    }
    return render(request, "profile.html", context)


# ── Favorite views ────────────────────────────────────────────


def _ensure_default_favorites(user):
    """Create Home and Work placeholder slots if they don't exist yet."""
    for slot in ("home", "work"):
        FavoriteLocation.objects.get_or_create(
            user=user, slot=slot,
            defaults={"label": slot.title()},
        )


@login_required
@require_POST
def save_favorite(request):
    """Create or update a favorite location."""
    fav_id = request.POST.get("fav_id")
    address = request.POST.get("address", "").strip()
    label = request.POST.get("label", "").strip()
    lat = request.POST.get("lat") or None
    lng = request.POST.get("lng") or None

    try:
        if lat:
            lat = float(lat)
        if lng:
            lng = float(lng)
    except (ValueError, TypeError):
        lat = lng = None

    if fav_id:
        # Updating existing slot
        try:
            fav = FavoriteLocation.objects.get(pk=fav_id, user=request.user)
            fav.address = address
            fav.lat = lat
            fav.lng = lng
            if label:
                fav.label = label
            fav.save()
        except FavoriteLocation.DoesNotExist:
            messages.error(request, "Favorite not found.")
    else:
        # Creating new custom slot — enforce max 2 custom
        custom_count = FavoriteLocation.objects.filter(user=request.user, slot="custom").count()
        if custom_count >= 2:
            messages.error(request, "You can save up to 2 custom favorites.")
        else:
            FavoriteLocation.objects.create(
                user=request.user,
                slot="custom",
                label=label or "Saved",
                address=address,
                lat=lat,
                lng=lng,
            )

    return redirect("rides:rider_search")


@login_required
@require_POST
def delete_favorite(request, pk):
    """Delete a custom favorite or clear a Home/Work slot."""
    try:
        fav = FavoriteLocation.objects.get(pk=pk, user=request.user)
    except FavoriteLocation.DoesNotExist:
        messages.error(request, "Favorite not found.")
        return redirect("rides:rider_search")

    if fav.slot == "custom":
        fav.delete()
    else:
        fav.address = ""
        fav.lat = None
        fav.lng = None
        fav.save()

    return redirect("rides:rider_search")


# ── Auth views ─────────────────────────────────────────────


def signup(request):
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            try:
                user = form.save()
                login(request, user)
                messages.success(request, "Welcome to OnTheWay!")
                return redirect("rides:index")
            except Exception:
                logger.exception("Error during signup")
                messages.error(request, "Something went wrong creating your account. Please try again.")
        else:
            messages.error(request, "Please fix the errors below.")
    else:
        form = SignUpForm()

    return render(request, "registration/signup.html", {"form": form})
