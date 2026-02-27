from django.contrib.auth import get_user_model


class EmailBackend:
    """
    Authenticate using email instead of username.

    Django's AuthenticationForm passes the identifier as `username`, so we
    treat that as an email address here.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None

        User = get_user_model()
        try:
            user = User.objects.get(email__iexact=username.strip())
        except User.DoesNotExist:
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None

    def get_user(self, user_id):
        User = get_user_model()
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None

    def user_can_authenticate(self, user):
        is_active = getattr(user, "is_active", None)
        return is_active or is_active is None

