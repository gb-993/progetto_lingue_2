"""
Django settings for progetto_lingua_2 project.
"""
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

# ---------------------- Helpers env ----------------------
def env(key, default=None):
    return os.environ.get(key, default)

def env_bool(key, default=False):
    v = os.environ.get(key)
    if v is None:
        return default
    return str(v).lower() in ("1", "true", "yes", "on")

def env_list(key, default=""):
    raw = os.environ.get(key, default)
    return [x.strip() for x in raw.split(",") if x.strip()]

# ---------------------- Base / Security ----------------------
SECRET_KEY = env("DJANGO_SECRET_KEY", "dev-insecure-change-me")
DEBUG = env_bool("DJANGO_DEBUG", False)
ENV = env("ENV", "dev")  # "dev" | "prod"

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
# CSRF: accetta host espliciti + derivati da ALLOWED_HOSTS
_csrf_from_env = env_list(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    "http://localhost,http://127.0.0.1,http://localhost:8000,http://127.0.0.1:8000"
)
_auto = []
for h in ALLOWED_HOSTS:
    if not h:
        continue
    _auto += [f"http://{h}", f"https://{h}"]
CSRF_TRUSTED_ORIGINS = list(dict.fromkeys(_csrf_from_env + _auto))  # dedup

SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", ENV == "prod")
SESSION_COOKIE_SECURE = ENV == "prod"
CSRF_COOKIE_SECURE = ENV == "prod"
# Se Nginx termina TLS e inoltra:
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

# ---------------------- Apps ----------------------
INSTALLED_APPS = [
    # Django core
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.postgres",
    'django.contrib.staticfiles',  


    # Project apps
    "core.apps.CoreConfig",
    "accounts",
    "languages_ui",
    "parameters_ui",
    "glossary_ui",
    "graphs_ui",
    "tablea_ui",
    "submissions_ui",
    "queries",
]
SUBMISSIONS_MAX_PER_LANGUAGE = 10

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "progetto_lingua_2.urls"

# ---------------------- Templates ----------------------
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "progetto_lingua_2.wsgi.application"

# ---------------------- Database (PostgreSQL) ----------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB"),
        "USER": env("POSTGRES_USER"),
        "PASSWORD": env("POSTGRES_PASSWORD"),
        "HOST": env("POSTGRES_HOST", "db"),
        "PORT": env("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": 60,  
    }
}

# ---------------------- Auth ----------------------
AUTH_USER_MODEL = "core.User"   
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "/accounts/login/"

# ---------------------- I18N / TZ ----------------------
LANGUAGE_CODE = "it-it"
TIME_ZONE = "Europe/Rome"
USE_I18N = True
USE_TZ = True

# ---------------------- Static / Media ----------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

if (BASE_DIR / "static").exists():
    STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"


STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------- Email / Password reset ----------------------

EMAIL_BACKEND = env("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "no-reply@example.test")
EMAIL_SUBJECT_PREFIX = env("EMAIL_SUBJECT_PREFIX", "[PCM] ")

# SMTP (solo se EMAIL_BACKEND è SMTP o analogo)
EMAIL_HOST = env("EMAIL_HOST", "")
EMAIL_PORT = int(env("EMAIL_PORT", "587")) if EMAIL_HOST else None
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)

# Token timeout reset password
PASSWORD_RESET_TIMEOUT = int(env("DJANGO_PASSWORD_RESET_TIMEOUT", 60 * 60 * 3))  


if ENV == "prod":
    
    SECURE_HSTS_SECONDS = int(env("DJANGO_SECURE_HSTS_SECONDS", 60 * 60 * 24 * 7))  
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", True)
    SECURE_HSTS_PRELOAD = env_bool("DJANGO_SECURE_HSTS_PRELOAD", True)
