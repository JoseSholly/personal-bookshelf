from .base import *
from ..env import BASE_DIR
from dotenv import load_dotenv
import os
from urllib.parse import parse_qsl, urlparse

load_dotenv()


# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv("SECRET_KEY", "django-insecure-default-key")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")


tmpPostgres = urlparse(os.getenv("DATABASE_URL"))

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": tmpPostgres.path.replace("/", ""),
        "USER": tmpPostgres.username,
        "PASSWORD": tmpPostgres.password,
        "HOST": tmpPostgres.hostname,
        "PORT": tmpPostgres.port,
        "OPTIONS": dict(parse_qsl(tmpPostgres.query)),
    }
}


# This production code might break development mode, so we check # This production code might break development mode, so we check whether we're in DEBUG mode
if not DEBUG:
    # Tell Django to copy static assets into a path called `staticfiles` (this is specific to Render)
    STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
    # Enable the WhiteNoise storage backend, which compresses static files to reduce disk use
    # and renames the files with unique names for each version to support long-term caching
    STATICFILES_STORAGE = "whitenoise.storage.CompressedStaticFilesStorage"
    WHITENOISE_AUTOREFRESH = True
    WHITENOISE_USE_FINDERS = True
    WHITENOISE_COMPRESS = True
    WHITENOISE_MANIFEST_STRICT = True

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"


STATIC_URL = "/static/"

SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"

SECURE_BROWSER_XSS_FILTER = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True


# pgvector is used for embeddings — no Railway volume or CHROMA_PERSIST_DIR needed.
