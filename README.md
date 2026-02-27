# OnTheWay

A ride-sharing web application where drivers can offer seats on trips they're already taking, and riders can search for and request rides. Built with Django, Leaflet maps, and OpenStreetMap-powered geocoding and routing.

## Features

- **Drive** — Offer rides with pickup, destination, departure time, seats, and optional price
- **Ride** — Search by origin, destination, or state; see matching rides on a map with detour estimates
- **My Requests** — Track ride requests and cancel pending ones
- **Ratings** — Rate completed rides on a 1–5 star smoothness scale; drivers can rate each rider and mark "no show"
- **Profiles** — Bio, avatar color, and average rating
- **Favorites** — Save Home, Work, and custom locations for quick search
- **Maps** — Interactive Leaflet maps with OSRM driving routes

### Rating Scale

| Stars | Meaning |
|-------|---------|
| 1 | Severely disrupted (comment required, flagged for review) |
| 2 | Slightly disrupted |
| 3 | Mostly smooth |
| 4 | Smooth |
| 5 | Very smooth |

## Tech Stack

- **Backend:** Django 3.1, SQLite
- **Frontend:** Leaflet, Flatpickr, vanilla JavaScript
- **APIs:** Nominatim (geocoding/autocomplete), OSRM (routing)

## Requirements

- Python 3.8+
- Django 3.1+

## Setup

```bash
# Create and activate a virtual environment (recommended)
python -m venv venv
source venv/bin/activate   # On Windows: venv\Scripts\activate

# Install Django
pip install django

# Run migrations
python manage.py migrate

# Create a superuser (optional, for admin access)
python manage.py createsuperuser

# Seed demo data (optional)
python manage.py seed_demo

# Run the development server
python manage.py runserver
```

Visit `http://127.0.0.1:8000/` in your browser.

## Demo Mode

When `DEBUG=True`, unauthenticated visitors are automatically logged in as a demo user. Sign out to use normal signup/login.

## Project Structure

```
OnTheWay/
├── manage.py
├── HandyRides/          # Django project config
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── rides/               # Main app
│   ├── models.py        # Ride, RideRequest, Profile, Rating, FavoriteLocation
│   ├── views.py
│   ├── forms.py
│   ├── urls.py
│   └── templates/
├── templates/           # Base templates
├── static/              # CSS, JS, images
│   ├── styles.css
│   ├── autocomplete.js
│   ├── ridemap.js
│   ├── livemap.js
│   ├── detour.js
│   └── datepicker.js
└── db.sqlite3
```

## Main URLs

| Path | Description |
|------|-------------|
| `/` | Splash / home |
| `/rides/` | Driver dashboard |
| `/rides/search/` | Search for rides |
| `/rides/my-requests/` | Your ride requests |
| `/rides/ratings/` | Rate completed rides |
| `/rides/profile/` | Your profile |
| `/accounts/login/` | Sign in |
| `/accounts/signup/` | Create account |
| `/admin/` | Django admin |

## License

MIT
