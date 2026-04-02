from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from common.env import env, env_bool, env_int, env_list, env_path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
PROJECT_ROOT = BASE_DIR.parent
STORAGE_ROOT = env_path("STORAGE_ROOT", "storage", base_dir=PROJECT_ROOT)
MEDIA_ROOT = env_path("MEDIA_ROOT", STORAGE_ROOT / "media", base_dir=PROJECT_ROOT)
TEMP_FILES_ROOT = env_path("TEMP_FILES_ROOT", STORAGE_ROOT / "tmp", base_dir=PROJECT_ROOT)
STATIC_ROOT = env_path("STATIC_ROOT", "runtime/staticfiles", base_dir=PROJECT_ROOT)

SECRET_KEY = env("DJANGO_SECRET_KEY", default="django-insecure-change-me", required=False)
DEBUG = env_bool("DJANGO_DEBUG", default=False)

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])
CORS_ALLOW_ALL_ORIGINS = env_bool("CORS_ALLOW_ALL_ORIGINS", default=False)
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", default=[])
CORS_ALLOWED_ORIGIN_REGEXES = env_list("CORS_ALLOWED_ORIGIN_REGEXES", default=[])
CORS_ALLOW_CREDENTIALS = env_bool("CORS_ALLOW_CREDENTIALS", default=True)

APP_SLUG = env("APP_SLUG", default="calidad-platform")
API_VERSION = env("API_VERSION", default="v1")
LANGUAGE_CODE = env("LANGUAGE_CODE", default="es-ar")
TIME_ZONE = env("TIME_ZONE", default="America/Argentina/Buenos_Aires")
USE_I18N = True
USE_TZ = True

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
]

LOCAL_APPS = [
    "apps.core.apps.CoreConfig",
    "apps.accounts.apps.AccountsConfig",
    "apps.catalog.apps.CatalogConfig",
    "apps.anomalies.apps.AnomaliesConfig",
    "apps.actions.apps.ActionsConfig",
    "apps.notifications.apps.NotificationsConfig",
    "apps.audit.apps.AuditConfig",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB", default="calidad"),
        "USER": env("POSTGRES_USER", default="calidad"),
        "PASSWORD": env("POSTGRES_PASSWORD", default="calidad"),
        "HOST": env("POSTGRES_HOST", default="localhost"),
        "PORT": env("POSTGRES_PORT", default="5432"),
        "CONN_MAX_AGE": env_int("POSTGRES_CONN_MAX_AGE", default=60),
        "OPTIONS": {},
    }
}

AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = [
    "apps.accounts.auth_backends.ScopedRolePermissionBackend",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LAST_ACTIVITY_UPDATE_WINDOW_SECONDS = env_int("LAST_ACTIVITY_UPDATE_WINDOW_SECONDS", default=300)

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.accounts.authentication.ActivityJWTAuthentication",
        "apps.accounts.authentication.ActivitySessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "common.permissions.IsAuthenticatedAndActive",
    ],
    "DEFAULT_PAGINATION_CLASS": "common.pagination.DefaultPageNumberPagination",
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.AnonRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": env("DRF_ANON_RATE", default="60/minute"),
        "user": env("DRF_USER_RATE", default="600/hour"),
        "login": env("DRF_LOGIN_RATE", default="10/minute"),
    },
    "PAGE_SIZE": 25,
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=env_int("JWT_ACCESS_TOKEN_MINUTES", default=15)),
    "REFRESH_TOKEN_LIFETIME": timedelta(minutes=env_int("JWT_REFRESH_TOKEN_MINUTES", default=480)),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

STATIC_URL = "/static/"
MEDIA_URL = "/media/"

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

FILE_UPLOAD_MAX_MEMORY_SIZE = env_int("FILE_UPLOAD_MAX_MEMORY_SIZE", default=5 * 1024 * 1024)
DATA_UPLOAD_MAX_MEMORY_SIZE = env_int("DATA_UPLOAD_MAX_MEMORY_SIZE", default=10 * 1024 * 1024)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
APPEND_SLASH = True

LOG_LEVEL = env("LOG_LEVEL", default="INFO")
LOG_TO_FILE = env_bool("DJANGO_LOG_TO_FILE", default=False)
LOG_DIR = env_path("LOG_DIR", "runtime/logs", base_dir=PROJECT_ROOT)
APP_LOG_FILE = env("APP_LOG_FILE", default=f"{APP_SLUG}.log")

if LOG_TO_FILE:
    LOG_DIR.mkdir(parents=True, exist_ok=True)

LOGGING_HANDLERS = {
    "console": {
        "class": "logging.StreamHandler",
        "formatter": "standard",
    },
}
ROOT_LOG_HANDLERS = ["console"]

if LOG_TO_FILE:
    LOGGING_HANDLERS["file"] = {
        "class": "logging.FileHandler",
        "formatter": "standard",
        "filename": str(LOG_DIR / APP_LOG_FILE),
        "encoding": "utf-8",
    }
    ROOT_LOG_HANDLERS.append("file")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s %(levelname)s [%(name)s] %(message)s",
        },
    },
    "handlers": LOGGING_HANDLERS,
    "root": {
        "handlers": ROOT_LOG_HANDLERS,
        "level": LOG_LEVEL,
    },
}
