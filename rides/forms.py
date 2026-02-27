from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import Profile, Ride


class RideCreateForm(forms.ModelForm):
    """
    Form used by drivers to create a new ride offer.
    Includes hidden lat/lng fields populated by the autocomplete JS.
    """

    departure_time = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
        input_formats=["%Y-%m-%dT%H:%M"],
        error_messages={
            "required": "Please pick a departure date and time.",
            "invalid": "Enter a valid date and time.",
        },
    )

    class Meta:
        model = Ride
        fields = [
            "origin",
            "destination",
            "destination_state",
            "departure_time",
            "total_seats",
            "price_per_seat",
            "max_detour_minutes",
            "notes",
            "origin_lat",
            "origin_lng",
            "dest_lat",
            "dest_lng",
            "route_polyline",
            "route_duration",
        ]
        widgets = {
            "origin": forms.TextInput(attrs={
                "data-autocomplete": "address",
                "data-lat-target": "id_origin_lat",
                "data-lng-target": "id_origin_lng",
                "autocomplete": "off",
                "placeholder": "e.g. Princeton University",
            }),
            "destination": forms.TextInput(attrs={
                "data-autocomplete": "address",
                "data-state-target": "id_destination_state",
                "data-lat-target": "id_dest_lat",
                "data-lng-target": "id_dest_lng",
                "autocomplete": "off",
                "placeholder": "e.g. Newark Airport (EWR)",
            }),
            "destination_state": forms.TextInput(attrs={
                "placeholder": "e.g. NJ",
                "maxlength": "2",
            }),
            "total_seats": forms.NumberInput(attrs={
                "min": "1",
                "max": "20",
                "placeholder": "1",
            }),
            "price_per_seat": forms.NumberInput(attrs={
                "min": "0",
                "step": "0.01",
                "placeholder": "0.00",
            }),
            "notes": forms.Textarea(attrs={
                "rows": 3,
                "placeholder": "Anything riders should know? (luggage space, music preference, etc.)",
            }),
            "origin_lat": forms.HiddenInput(),
            "origin_lng": forms.HiddenInput(),
            "dest_lat": forms.HiddenInput(),
            "dest_lng": forms.HiddenInput(),
            "route_polyline": forms.HiddenInput(),
            "route_duration": forms.HiddenInput(),
            "max_detour_minutes": forms.NumberInput(attrs={
                "type": "range",
                "min": "0",
                "max": "30",
                "step": "1",
                "class": "detour-slider",
            }),
        }
        error_messages = {
            "origin": {
                "required": "Please enter a pickup location.",
                "max_length": "Location name is too long (max 256 characters).",
            },
            "destination": {
                "required": "Please enter a destination.",
                "max_length": "Location name is too long (max 256 characters).",
            },
            "total_seats": {
                "required": "How many seats are available?",
                "invalid": "Enter a whole number for seats.",
            },
        }
        labels = {
            "origin": "Pickup / Starting point",
            "destination": "Destination",
            "destination_state": "Destination state (2-letter)",
            "departure_time": "Departure date & time",
            "total_seats": "Available seats",
            "price_per_seat": "Price per seat (optional)",
            "max_detour_minutes": "Max detour to pick up riders",
            "notes": "Notes for riders (optional)",
        }

    def clean_destination_state(self):
        state = self.cleaned_data.get("destination_state", "").strip()
        if state and len(state) != 2:
            raise forms.ValidationError("Enter a 2-letter state code (e.g. NJ, NY).")
        return state.upper() if state else ""

    def clean_total_seats(self):
        seats = self.cleaned_data.get("total_seats")
        if seats is not None and seats < 1:
            raise forms.ValidationError("You need at least 1 available seat.")
        if seats is not None and seats > 20:
            raise forms.ValidationError("Maximum 20 seats per ride.")
        return seats

    def clean_price_per_seat(self):
        price = self.cleaned_data.get("price_per_seat")
        if price is not None and price < 0:
            raise forms.ValidationError("Price can't be negative.")
        return price

    def clean_departure_time(self):
        dt = self.cleaned_data.get("departure_time")
        if dt and dt < timezone.now():
            raise forms.ValidationError("Departure time must be in the future.")
        return dt


class RideSearchForm(forms.Form):
    """
    Rider search: filter open rides by origin, destination, and/or state.
    When lat/lng are provided (via autocomplete), proximity search (~1 mile)
    is used instead of text matching.
    """

    origin = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            "class": "search-input",
            "placeholder": "Pickup location",
            "autocomplete": "off",
            "data-autocomplete": "address",
            "data-lat-target": "id_origin_lat",
            "data-lng-target": "id_origin_lng",
        }),
    )
    destination = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            "class": "search-input",
            "placeholder": "Where to?",
            "autocomplete": "off",
            "data-autocomplete": "address",
            "data-state-target": "id_state",
            "data-lat-target": "id_dest_lat",
            "data-lng-target": "id_dest_lng",
        }),
    )
    state = forms.CharField(
        required=False,
        max_length=2,
        widget=forms.TextInput(attrs={
            "class": "search-input",
            "placeholder": "State (e.g. NJ)",
            "autocomplete": "off",
        }),
    )
    # Hidden fields populated by autocomplete to enable proximity search
    origin_lat = forms.FloatField(required=False, widget=forms.HiddenInput())
    origin_lng = forms.FloatField(required=False, widget=forms.HiddenInput())
    dest_lat = forms.FloatField(required=False, widget=forms.HiddenInput())
    dest_lng = forms.FloatField(required=False, widget=forms.HiddenInput())

    def clean_state(self):
        state = self.cleaned_data.get("state", "").strip()
        if state and len(state) != 2:
            raise forms.ValidationError("Enter a 2-letter state code (e.g. NJ, NY).")
        return state.upper() if state else ""

    def has_query(self):
        return any(
            self.cleaned_data.get(f)
            for f in ("origin", "destination", "state")
        )


class SignUpForm(UserCreationForm):
    """
    Sign up with name, email, and password.
    """

    name = forms.CharField(
        required=True,
        label="Name",
        max_length=150,
        error_messages={"required": "Please enter your name."},
    )
    username = forms.EmailField(
        required=True,
        label="Email",
        error_messages={
            "required": "Please enter your email address.",
            "invalid": "Enter a valid email address.",
        },
    )

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ("name", "username")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget = forms.EmailInput(attrs={
            "autocomplete": "email",
            "placeholder": "you@example.com",
        })
        self.fields["name"].widget.attrs.update({
            "autocomplete": "name",
            "placeholder": "Your name",
        })
        self.fields["password1"].help_text = "At least 8 characters."
        self.fields["password1"].widget.attrs["placeholder"] = "Create a password"
        self.fields["password2"].widget.attrs["placeholder"] = "Confirm your password"
        self.fields["password1"].error_messages["required"] = "Please create a password."
        self.fields["password2"].error_messages["required"] = "Please confirm your password."

    def clean_username(self):
        email = self.cleaned_data["username"].strip().lower()
        User = get_user_model()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("An account with this email already exists.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        email = self.cleaned_data["username"].strip().lower()
        user.username = email
        user.email = email
        user.first_name = self.cleaned_data["name"].strip()
        if commit:
            user.save()
        return user


class ProfileForm(forms.ModelForm):
    """
    Let users edit their bio blurb.
    """

    class Meta:
        model = Profile
        fields = ["bio"]
        widgets = {
            "bio": forms.Textarea(attrs={
                "rows": 4,
                "placeholder": "Tell riders and drivers a little about yourself...",
            }),
        }
        labels = {
            "bio": "About you",
        }


STAR_CHOICES = [
    (1, "1 – Severely disrupted (comment required)"),
    (2, "2 – Slightly disrupted"),
    (3, "3 – Mostly smooth"),
    (4, "4 – Smooth"),
    (5, "5 – Very smooth"),
]


class RatingForm(forms.Form):
    """Form for submitting a ride smoothness rating."""

    stars = forms.TypedChoiceField(
        choices=STAR_CHOICES,
        coerce=int,
        required=False,
        widget=forms.RadioSelect(attrs={"class": "rating-stars"}),
    )
    did_not_show_up = forms.BooleanField(required=False, initial=False)
    comment = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Describe the problem (required for 1-star ratings)..."}),
    )

    def __init__(self, *args, is_driver_rating=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.is_driver_rating = is_driver_rating
        if not is_driver_rating:
            del self.fields["did_not_show_up"]

    def clean(self):
        data = super().clean()
        did_not_show_up = data.get("did_not_show_up", False)
        stars = data.get("stars")
        comment = (data.get("comment") or "").strip()

        if did_not_show_up:
            if self.is_driver_rating:
                return data
            self.add_error("did_not_show_up", "Only drivers can mark 'did not show up'.")

        if not stars and not did_not_show_up:
            self.add_error("stars", "Please select a rating or mark 'did not show up'.")
            return data

        if stars == 1 and not comment:
            self.add_error("comment", "A comment is required for severely disrupted rides.")
        return data


class EmailAuthenticationForm(AuthenticationForm):
    """
    Authentication form that prompts for Email + Password.
    """

    username = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={
            "autofocus": True,
            "autocomplete": "email",
            "placeholder": "you@example.com",
        }),
        error_messages={
            "required": "Please enter your email.",
            "invalid": "Enter a valid email address.",
        },
    )

    error_messages = {
        "invalid_login": "Incorrect email or password. Please try again.",
        "inactive": "This account has been deactivated.",
    }
