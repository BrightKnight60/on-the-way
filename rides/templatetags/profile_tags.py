"""
Template tags for rendering user profile chips with avatar initials.

Usage:
    {% load profile_tags %}
    {% user_chip some_user %}
"""
from django import template
from django.utils.html import format_html

register = template.Library()

_COLORS = [
    "#4f46e5", "#dc2626", "#16a34a", "#ea580c", "#0891b2",
    "#7c3aed", "#ca8a04", "#db2777", "#059669", "#0d9488",
]


def _get_profile_data(user):
    """Return (initial, color) for a user, creating Profile if needed."""
    # Lazy import to avoid circular imports at module load time
    from rides.models import Profile

    try:
        profile = user.profile
    except (Profile.DoesNotExist, Exception):
        try:
            profile, _ = Profile.objects.get_or_create(user=user)
        except Exception:
            # Fallback if DB not ready
            name = getattr(user, "first_name", "") or getattr(user, "username", "?")
            return name[0].upper() if name else "?", _COLORS[0]

    initial = profile.initial
    color = profile.avatar_color or _COLORS[user.pk % len(_COLORS)]
    return initial, color


@register.simple_tag
def user_chip(user):
    """
    Render an inline clickable chip: coloured avatar circle + name.
    Links to the user's public profile page.
    """
    if not user:
        return ""
    initial, color = _get_profile_data(user)
    name = user.first_name or user.username
    return format_html(
        '<a href="/rides/profile/{uid}/" class="user-chip">'
        '<span class="user-chip-avatar" style="background:{color};">{initial}</span>'
        '<span>{name}</span>'
        '</a>',
        uid=user.pk,
        color=color,
        initial=initial,
        name=name,
    )


@register.simple_tag
def user_color(user):
    """Return just the avatar colour hex string for a user."""
    if not user:
        return _COLORS[0]
    _, color = _get_profile_data(user)
    return color


@register.simple_tag
def avatar_circle(user, size="sm"):
    """
    Render just the circle avatar (no name, no link).
    size: "sm" (20px) or "md" (32px) or "lg" (48px).
    """
    if not user:
        return ""
    initial, color = _get_profile_data(user)
    sizes = {"sm": "20px", "md": "32px", "lg": "48px"}
    fonts = {"sm": "0.6rem", "md": "0.85rem", "lg": "1.1rem"}
    px = sizes.get(size, sizes["sm"])
    fs = fonts.get(size, fonts["sm"])
    return format_html(
        '<span class="user-chip-avatar" style="background:{color};width:{px};height:{px};font-size:{fs};">'
        '{initial}</span>',
        color=color, px=px, fs=fs, initial=initial,
    )
