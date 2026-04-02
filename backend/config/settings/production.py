from common.env import ImproperEnvironmentError, env

from .base import *  # noqa: F403,F401

SECRET_KEY = env("DJANGO_SECRET_KEY", required=True)
if SECRET_KEY in {"django-insecure-change-me", "calidad-platform-2026-local-secret-change-this"} or len(SECRET_KEY) < 32:
    raise ImproperEnvironmentError("DJANGO_SECRET_KEY insegura para produccion.")

DEBUG = False
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
