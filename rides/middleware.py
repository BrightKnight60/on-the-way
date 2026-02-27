from django.contrib.auth import get_user_model, login


class AutoLoginDemoMiddleware:
    """
    Automatically creates and logs in a 'demo' user when an
    unauthenticated visitor hits the site for the first time.

    Respects explicit logout: when a user signs out, a cookie is set
    so the middleware stops auto-logging-in until the browser is closed
    or the cookie is cleared.
    """

    DEMO_EMAIL = "alain@princeton.edu"
    DEMO_NAME = "Alain Kornhauser"
    DEMO_PASSWORD = "demo1234"
    COOKIE_NAME = "skip_demo_login"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from django.conf import settings

        if (
            settings.DEBUG
            and not request.user.is_authenticated
            and not request.COOKIES.get(self.COOKIE_NAME)
        ):
            path = request.path
            # Skip for static files, admin, and the logout URL
            skip_prefixes = ("/static/", "/admin/", "/accounts/logout/")
            if not any(path.startswith(p) for p in skip_prefixes):
                User = get_user_model()
                user, created = User.objects.get_or_create(
                    username=self.DEMO_EMAIL,
                    defaults={
                        "email": self.DEMO_EMAIL,
                        "first_name": self.DEMO_NAME.split()[0],
                        "last_name": self.DEMO_NAME.split()[-1],
                    },
                )
                if created:
                    user.set_password(self.DEMO_PASSWORD)
                    user.save()

                login(request, user)

        response = self.get_response(request)

        # When the user hits the logout URL, set a cookie so we stop
        # auto-logging-in. The cookie is a session cookie (no max_age)
        # so it clears when the browser closes.
        if request.path == "/accounts/logout/":
            response.set_cookie(self.COOKIE_NAME, "1", samesite="Lax")

        return response
