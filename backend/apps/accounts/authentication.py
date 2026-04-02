from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.authentication import SessionAuthentication
from rest_framework_simplejwt.authentication import JWTAuthentication

UserModel = get_user_model()



def touch_last_activity(user) -> None:
    if not user or not user.is_authenticated:
        return

    now = timezone.now()
    last_activity = getattr(user, "last_activity_at", None)
    update_window = getattr(settings, "LAST_ACTIVITY_UPDATE_WINDOW_SECONDS", 300)

    if last_activity and (now - last_activity).total_seconds() < update_window:
        return

    UserModel.objects.filter(pk=user.pk).update(last_activity_at=now)
    user.last_activity_at = now


class ActivitySessionAuthentication(SessionAuthentication):
    def authenticate(self, request):
        result = super().authenticate(request)
        if result is None:
            return None

        user, auth = result
        touch_last_activity(user)
        return user, auth


class ActivityJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        result = super().authenticate(request)
        if result is None:
            return None

        user, token = result
        touch_last_activity(user)
        return user, token
