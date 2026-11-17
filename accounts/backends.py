
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailBackend(ModelBackend):

    def authenticate(self, request, username=None, password=None, **kwargs):
        User = get_user_model()

        identifier = username or kwargs.get("email")

        if identifier is None or password is None:
            return None

        try:
            user = User.objects.get(username__iexact=identifier)
        except User.DoesNotExist:
            try:
                user = User.objects.get(email__iexact=identifier)
            except User.DoesNotExist:
                return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user

        return None
