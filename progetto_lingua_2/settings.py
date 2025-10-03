"""
Django settings for progetto_lingua_2 project.
"""
import os
def env(key, default=None): return os.environ.get(key, default)

from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

# ---------------------- Base / Security ----------------------
SECRET_KEY = env("DJANGO_SECRET_KEY", "dev-insecure-change-me")
DEBUG = env("DJANGO_DEBUG", "0") == "1"
ALLOWED_HOSTS = [h.strip() for h in env("DJANGO_ALLOWED_HOSTS","localhost,127.0.0.1").split(",") if h.strip()]
CSRF_TRUSTED_ORIGINS = [env("DJANGO_CSRF_TRUSTED_ORIGINS","http://localhost")]
SECURE_SSL_REDIRECT = env("DJANGO_SECURE_SSL_REDIRECT","0") == "1"


# ---------------------- Apps ----------------------
INSTALLED_APPS = [
    # Django core
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "core.apps.CoreConfig",


    # Project apps
    "accounts",
    "languages_ui",
    "parameters_ui",
    "glossary_ui",
    "tablea_ui",
    "submissions_ui",

]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",

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
        "CONN_MAX_AGE": 60,  # pooling semplice
    }
}


# ---------------------- Auth ----------------------
AUTH_USER_MODEL = "core.User"   # <— Custom user basato su email

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
STATIC_ROOT = BASE_DIR / "staticfiles"    # -> /app/staticfiles (montato in Nginx)
# Se nel repo hai una cartella "static/" con asset sorgente, abilita questa riga:
STATICFILES_DIRS = [ BASE_DIR / "static" ]
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
# WhiteNoise è opzionale con Nginx, ma se lo tieni:
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"



# ---------------------- Default PK ----------------------
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------- Dev helpers ----------------------
def envlist(key, default=""):
    raw = os.environ.get(key, default)
    return [x.strip() for x in raw.split(",") if x.strip()]

# DEBUG da env
DEBUG = os.environ.get("DJANGO_DEBUG", "0") in ("1", "true", "True")

# Hosts e origini fidate da env (virgola-separate)
ALLOWED_HOSTS = envlist("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")

# Base da env, puoi aggiungere domini reali in produzione (es. https://mio.dominio.it)
_csrf_from_env = envlist(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    "http://localhost,http://127.0.0.1,http://localhost:8080,http://127.0.0.1:8080"
)

# Costruiamo anche varianti utili automaticamente
_auto = []
for h in ALLOWED_HOSTS:
    if not h:
        continue
    # senza porta
    _auto += [f"http://{h}", f"https://{h}"]
    # porte comuni in dev
    _auto += [f"http://{h}:8080", f"http://{h}:8000"]

# Unione (ordinale) tra env e auto
_seen = set()
CSRF_TRUSTED_ORIGINS = []
for v in _csrf_from_env + _auto:
    if v not in _seen:
        CSRF_TRUSTED_ORIGINS.append(v)
        _seen.add(v)

# Cookie non secure in dev (su HTTP)
if DEBUG:
    CSRF_COOKIE_SECURE = False
    SESSION_COOKIE_SECURE = False

# (Se Nginx termina HTTPS e fa proxy verso Django)
# SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
# USE_X_FORWARDED_HOST = True
