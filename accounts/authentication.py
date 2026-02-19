from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        try:
            user = UserModel.objects.filter(email__iexact=username).first()
        except UserModel.DoesNotExist:
            return None
        else:
            if (
                user
                and user.check_password(password)
                and self.user_can_authenticate(user)
            ):
                return user
        return None
