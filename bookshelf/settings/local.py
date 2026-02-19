from .base import *
from ..env import BASE_DIR
from dotenv import load_dotenv
from decouple import config
import os

load_dotenv()


# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv("SECRET_KEY", "django-insecure-local-key")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['*']



DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("POSTGRESQL_DB_NAME"),
        "USER": config("POSTGRESQL_DB_USER"),
        "PASSWORD": config("POSTGRESQL_DB_PASSWORD"),
        "HOST": config("POSTGRESQL_DB_HOST"),
        "PORT": config("POSTGRESQL_DB_PORT"),
        "CONN_MAX_AGE": 600,
    }
}


MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"


STATIC_URL = "/static/"

CHROMA_PERSIST_DIR = str(BASE_DIR / "chroma_db")