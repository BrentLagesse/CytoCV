"""Django settings for CytoCV."""

from pathlib import Path
import os

from accounts.quota_config import (
    BYTES_PER_MB,
    parse_quota_mb_value,
    parse_quota_suffixes,
    parse_user_fixed_quota_map,
)
from django.core.exceptions import ImproperlyConfigured

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent


def _read_env_file(path: Path) -> dict[str, str]:
    """Read simple KEY=VALUE pairs from a .env file."""
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        values[key] = value
    return values


def _load_env_file(path: Path) -> None:
    """Load simple KEY=VALUE pairs from a .env file without overriding os.environ."""
    for key, value in _read_env_file(path).items():
        if key in os.environ:
            continue
        os.environ[key] = value


_ENV_FILE_VALUES: dict[str, str] = {}
for env_path in (PROJECT_ROOT / ".env", BASE_DIR / ".env"):
    for env_key, env_value in _read_env_file(env_path).items():
        _ENV_FILE_VALUES.setdefault(env_key, env_value)


_load_env_file(PROJECT_ROOT / ".env")
_load_env_file(BASE_DIR / ".env")


def _get_env(
    var_name: str,
    default: str | None = None,
    *,
    prefer_env_file: bool = False,
) -> str | None:
    """Return a setting from the process environment, optionally preferring .env."""
    if prefer_env_file and var_name in _ENV_FILE_VALUES:
        return _ENV_FILE_VALUES[var_name]
    return os.getenv(var_name, default)


def _parse_env_bool(
    var_name: str,
    default: bool = False,
    *,
    prefer_env_file: bool = False,
) -> bool:
    """Parse common boolean env values with strict validation."""
    raw_value = _get_env(var_name, prefer_env_file=prefer_env_file)
    if raw_value is None:
        return default
    value = raw_value.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ImproperlyConfigured(
        f"{var_name} must be a boolean value (1/0, true/false, yes/no, on/off)."
    )


def _parse_env_int(
    var_name: str,
    default: int,
    *,
    prefer_env_file: bool = False,
) -> int:
    """Parse integer env values with strict validation."""
    raw_value = _get_env(var_name, prefer_env_file=prefer_env_file)
    if raw_value is None or raw_value.strip() == "":
        return default
    try:
        return int(raw_value.strip())
    except ValueError as exc:
        raise ImproperlyConfigured(f"{var_name} must be an integer.") from exc


def _parse_env_choice(
    var_name: str,
    default: str,
    *,
    allowed_values: tuple[str, ...],
    prefer_env_file: bool = False,
) -> str:
    """Parse a string env var constrained to a fixed set of choices."""

    raw_value = _get_env(var_name, prefer_env_file=prefer_env_file)
    if raw_value is None or raw_value.strip() == "":
        return default
    value = raw_value.strip().lower()
    if value not in allowed_values:
        allowed = ", ".join(allowed_values)
        raise ImproperlyConfigured(f"{var_name} must be one of: {allowed}.")
    return value


# Media storage
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Core settings (override in production)
SECRET_KEY = os.getenv("CYTOCV_SECRET_KEY", "django-insecure-change-me-in-env")
DEBUG = os.getenv("CYTOCV_DEBUG", "1") == "1"
SEGMENT_SAVE_DEBUG_ARTIFACTS = _parse_env_bool(
    "CYTOCV_SEGMENT_SAVE_DEBUG_ARTIFACTS",
    default=False,
)
ANALYSIS_EXECUTION_MODE = _parse_env_choice(
    "CYTOCV_ANALYSIS_EXECUTION_MODE",
    default="sync",
    allowed_values=("sync", "worker"),
)
ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("CYTOCV_ALLOWED_HOSTS", "").split(",")
    if host.strip()
]

_INSECURE_SECRET_KEY_VALUES = {
    "django-insecure-change-me-in-env",
    "change-me",
    "your-secret-key",
    "secret",
}
if not DEBUG:
    normalized_secret_key = SECRET_KEY.strip()
    if (
        not normalized_secret_key
        or normalized_secret_key.lower() in _INSECURE_SECRET_KEY_VALUES
    ):
        raise ImproperlyConfigured(
            "CYTOCV_SECRET_KEY must be set to a strong, non-default value "
            "when CYTOCV_DEBUG=0."
        )

# Authentication
AUTH_USER_MODEL = 'accounts.CustomUser'

AUTHENTICATION_BACKENDS = [
    # Email-based authentication
    'accounts.backends.EmailBackend',

    # Allauth auth methods (email/social)
    'allauth.account.auth_backends.AuthenticationBackend',
]

SOCIALACCOUNT_ADAPTER = "accounts.adapters.CustomSocialAccountAdapter"
# Allow social providers to auto-create/link accounts when a verified email is present.
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_QUERY_EMAIL = True
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_QUERY_EMAIL = True

# Apps
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    "django_tables2",
    'core',
    'accounts',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'allauth.socialaccount.providers.microsoft',
]

# Middleware
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'core.middleware.security_headers.ContentSecurityPolicyMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    "allauth.account.middleware.AccountMiddleware",
]

# Cache
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": BASE_DIR / 'cache',
    },

    # Optional: memcached backend
    #"default": {
    #    "BACKEND": "django.core.cache.backends.memcached.PyMemcacheCache",
    #    "LOCATION": "127.0.0.1:11211",
    #}

}

# URL routing
ROOT_URLCONF = 'cytocv.urls'

# Templates
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / "templates"],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.media',
                'django.template.context_processors.request',
            ],
        },
    },
]

# WSGI
WSGI_APPLICATION = 'cytocv.wsgi.application'


# Database policy:
# - sqlite is supported for local development/testing convenience.
# - postgres is required for production (enforced when CYTOCV_DEBUG=0).
DB_BACKEND = os.getenv("CYTOCV_DB_BACKEND", "").strip().lower()
if not DB_BACKEND:
    raise ImproperlyConfigured(
        "CYTOCV_DB_BACKEND is required and must be set to 'sqlite' or 'postgres'."
    )
if DB_BACKEND not in {"sqlite", "postgres"}:
    raise ImproperlyConfigured(
        "CYTOCV_DB_BACKEND must be one of: sqlite, postgres."
    )

if DB_BACKEND == "sqlite":
    if not DEBUG:
        raise ImproperlyConfigured(
            "SQLite is not allowed when CYTOCV_DEBUG=0. "
            "Set CYTOCV_DB_BACKEND=postgres for production."
        )
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    required_postgres_settings = (
        "CYTOCV_DB_NAME",
        "CYTOCV_DB_USER",
        "CYTOCV_DB_PASSWORD",
    )
    missing_postgres_settings = [
        key for key in required_postgres_settings if not os.getenv(key, "").strip()
    ]
    if missing_postgres_settings:
        raise ImproperlyConfigured(
            "Missing required PostgreSQL settings: "
            + ", ".join(missing_postgres_settings)
        )

    postgres_host = os.getenv("CYTOCV_DB_HOST", "127.0.0.1").strip() or "127.0.0.1"
    postgres_port = str(_parse_env_int("CYTOCV_DB_PORT", 5432))
    postgres_conn_max_age = _parse_env_int("CYTOCV_DB_CONN_MAX_AGE", 60)
    postgres_atomic_requests = _parse_env_bool("CYTOCV_DB_ATOMIC_REQUESTS", False)
    postgres_sslmode = os.getenv("CYTOCV_DB_SSLMODE", "prefer").strip() or "prefer"

    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("CYTOCV_DB_NAME", "").strip(),
            "USER": os.getenv("CYTOCV_DB_USER", "").strip(),
            "PASSWORD": os.getenv("CYTOCV_DB_PASSWORD", ""),
            "HOST": postgres_host,
            "PORT": postgres_port,
            "CONN_MAX_AGE": postgres_conn_max_age,
            "ATOMIC_REQUESTS": postgres_atomic_requests,
            "OPTIONS": {
                "sslmode": postgres_sslmode,
            },
        }
    }

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# OAuth / provider settings from environment
GOOGLE_OAUTH_CLIENT_ID = os.getenv("CYTOCV_GOOGLE_CLIENT_ID", "")
GOOGLE_OAUTH_CLIENT_SECRET = os.getenv("CYTOCV_GOOGLE_CLIENT_SECRET", "")
MICROSOFT_OAUTH_CLIENT_ID = os.getenv("CYTOCV_MICROSOFT_CLIENT_ID", "")
MICROSOFT_OAUTH_CLIENT_SECRET = os.getenv("CYTOCV_MICROSOFT_CLIENT_SECRET", "")
MICROSOFT_OAUTH_TENANT = os.getenv("CYTOCV_MICROSOFT_TENANT", "organizations")
MICROSOFT_OAUTH_LOGIN_URL = os.getenv(
    "CYTOCV_MICROSOFT_LOGIN_URL",
    "https://login.microsoftonline.com",
)

# Social auth providers
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        # For each OAuth based provider, either add a ``SocialApp``
        # (``socialaccount`` app) containing the required client
        # credentials, or list them here:
        'APP': {
            'client_id': GOOGLE_OAUTH_CLIENT_ID,
            'secret': GOOGLE_OAUTH_CLIENT_SECRET,
            'key': ''
        },
        'SCOPE': ['profile', 'email']
    },
    "microsoft": {
        "APPS": [
            {
                "client_id": MICROSOFT_OAUTH_CLIENT_ID,
                "secret": MICROSOFT_OAUTH_CLIENT_SECRET,
                "settings": {
                    "tenant": MICROSOFT_OAUTH_TENANT,
                    "login_url": MICROSOFT_OAUTH_LOGIN_URL,
                },
                'OAUTH_PKCE_ENABLED': True,
            }
        ],
    }
}

# OAuth provider redirects
SOCIALACCOUNT_LOGIN_ON_GET = False

# Allauth account configuration for email-only authentication.
ACCOUNT_USER_MODEL_EMAIL_FIELD = 'email'
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = os.getenv(
    "CYTOCV_ACCOUNT_EMAIL_VERIFICATION",
    "none" if DEBUG else "optional",
).strip().lower()
if ACCOUNT_EMAIL_VERIFICATION not in {"none", "optional", "mandatory"}:
    raise ImproperlyConfigured(
        "CYTOCV_ACCOUNT_EMAIL_VERIFICATION must be one of: none, optional, mandatory."
    )

LOGIN_URL = "signin"
LOGIN_REDIRECT_URL = "dashboard"

# Login rate limiting
LOGIN_RATE_LIMIT_MAX_ATTEMPTS = 15
LOGIN_RATE_LIMIT_WINDOW_SECONDS = 600
LOGIN_RATE_LIMIT_DEBUG_WINDOW_SECONDS = 60

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True
SITE_ID = 1
SOCIALACCOUNT_LOGIN_ON_GET = False

# Static files
STATIC_URL = 'static/'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Email
EMAIL_BACKEND = (_get_env(
    "CYTOCV_EMAIL_BACKEND",
    "django.core.mail.backends.smtp.EmailBackend",
    prefer_env_file=True,
) or "").strip() or "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = (_get_env("CYTOCV_EMAIL_HOST", "127.0.0.1", prefer_env_file=True) or "").strip()
EMAIL_HOST_USER = (_get_env(
    "CYTOCV_EMAIL_HOST_USER",
    "",
    prefer_env_file=True,
) or "").strip()
EMAIL_HOST_PASSWORD = (_get_env(
    "CYTOCV_EMAIL_HOST_PASSWORD",
    "",
    prefer_env_file=True,
) or "").strip()
EMAIL_PORT = _parse_env_int("CYTOCV_EMAIL_PORT", 25, prefer_env_file=True)
EMAIL_USE_TLS = _parse_env_bool("CYTOCV_EMAIL_USE_TLS", False, prefer_env_file=True)
EMAIL_USE_SSL = _parse_env_bool("CYTOCV_EMAIL_USE_SSL", False, prefer_env_file=True)
if EMAIL_USE_TLS and EMAIL_USE_SSL:
    raise ImproperlyConfigured(
        "CYTOCV_EMAIL_USE_TLS and CYTOCV_EMAIL_USE_SSL cannot both be enabled."
    )
_email_timeout_raw = (_get_env("CYTOCV_EMAIL_TIMEOUT", "", prefer_env_file=True) or "").strip()
EMAIL_TIMEOUT = (
    _parse_env_int("CYTOCV_EMAIL_TIMEOUT", 0, prefer_env_file=True)
    if _email_timeout_raw
    else None
)
_default_from_email = (_get_env(
    "CYTOCV_DEFAULT_FROM_EMAIL",
    "",
    prefer_env_file=True,
) or "").strip()
DEFAULT_FROM_EMAIL = _default_from_email or EMAIL_HOST_USER
EMAIL_REPLY_TO = ((_get_env(
    "CYTOCV_EMAIL_REPLY_TO",
    "",
    prefer_env_file=True,
) or "").strip()) or DEFAULT_FROM_EMAIL

if ACCOUNT_EMAIL_VERIFICATION != "none" and not DEFAULT_FROM_EMAIL:
    raise ImproperlyConfigured(
        "Configure CYTOCV_DEFAULT_FROM_EMAIL or CYTOCV_EMAIL_HOST_USER "
        "when email verification is enabled."
    )

# Storage quota policy
STORAGE_QUOTA_DEFAULT_MB = parse_quota_mb_value(
    raw_value=_get_env("CYTOCV_QUOTA_DEFAULT_MB", "100", prefer_env_file=True),
    var_name="CYTOCV_QUOTA_DEFAULT_MB",
)
STORAGE_QUOTA_EDU_MB = parse_quota_mb_value(
    raw_value=_get_env("CYTOCV_QUOTA_EDU_MB", "1024", prefer_env_file=True),
    var_name="CYTOCV_QUOTA_EDU_MB",
)
STORAGE_QUOTA_DEFAULT_BYTES = STORAGE_QUOTA_DEFAULT_MB * BYTES_PER_MB
STORAGE_QUOTA_EDU_BYTES = STORAGE_QUOTA_EDU_MB * BYTES_PER_MB
STORAGE_QUOTA_EDU_SUFFIXES = parse_quota_suffixes(
    _get_env("CYTOCV_QUOTA_EDU_SUFFIXES", ".edu", prefer_env_file=True),
)
STORAGE_QUOTA_USER_FIXED_BYTES = parse_user_fixed_quota_map(
    _get_env("CYTOCV_QUOTA_USER_FIXED_MB", "", prefer_env_file=True),
)

# Google reCAPTCHA
RECAPTCHA_ENABLED = os.getenv("CYTOCV_RECAPTCHA_ENABLED", "0") == "1"
RECAPTCHA_SITE_KEY = os.getenv("CYTOCV_RECAPTCHA_SITE_KEY", "")
RECAPTCHA_SECRET_KEY = os.getenv("CYTOCV_RECAPTCHA_SECRET_KEY", "")
_recaptcha_default_verify_url = "https://www.google.com/recaptcha/api/siteverify"
_recaptcha_override_allowed = os.getenv("CYTOCV_RECAPTCHA_ALLOW_VERIFY_URL_OVERRIDE", "0") == "1"
if DEBUG or _recaptcha_override_allowed:
    RECAPTCHA_VERIFY_URL = os.getenv(
        "CYTOCV_RECAPTCHA_VERIFY_URL",
        _recaptcha_default_verify_url,
    )
else:
    RECAPTCHA_VERIFY_URL = _recaptcha_default_verify_url
_raw_recaptcha_hosts = os.getenv("CYTOCV_RECAPTCHA_EXPECTED_HOSTNAMES", "")
if _raw_recaptcha_hosts.strip():
    RECAPTCHA_EXPECTED_HOSTNAMES = tuple(
        host.strip().lower()
        for host in _raw_recaptcha_hosts.split(",")
        if host.strip()
    )
elif DEBUG:
    RECAPTCHA_EXPECTED_HOSTNAMES = ("localhost", "127.0.0.1")
else:
    RECAPTCHA_EXPECTED_HOSTNAMES = tuple(
        host.strip().lower()
        for host in ALLOWED_HOSTS
        if host.strip() and host != "*"
    )

# Content Security Policy (CSP)
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = (
    "'self'",
    "'unsafe-inline'",
    "https://cdn.jsdelivr.net",
    "https://www.google.com/recaptcha/",
    "https://www.gstatic.com/recaptcha/",
)
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'", "https://fonts.googleapis.com")
CSP_IMG_SRC = ("'self'", "data:", "blob:")
CSP_FONT_SRC = ("'self'", "https://fonts.gstatic.com")
CSP_CONNECT_SRC = ("'self'", "https://www.google.com/recaptcha/")
CSP_FRAME_SRC = (
    "'self'",
    "https://www.google.com/recaptcha/",
    "https://recaptcha.google.com/recaptcha/",
)
CSP_FRAME_ANCESTORS = ("'none'",)
CSP_BASE_URI = ("'self'",)
CSP_FORM_ACTION = ("'self'", "https://accounts.google.com", "https://login.microsoftonline.com")
CSP_OBJECT_SRC = ("'none'",)

# Security profile toggles (defaults to not DEBUG; override with CYTOCV_SECURITY_STRICT)
_security_strict_env = os.getenv("CYTOCV_SECURITY_STRICT")
if _security_strict_env is None or _security_strict_env.strip() == "":
    SECURITY_STRICT = not DEBUG
else:
    SECURITY_STRICT = _security_strict_env.strip().lower() in ("1", "true", "yes", "on")
SECURITY_RATE_LIMIT_ENABLED = os.getenv("CYTOCV_RATE_LIMIT_ENABLED", "1") == "1"
SECURITY_RATE_LIMIT = {
    "mode": os.getenv("CYTOCV_RATE_LIMIT_MODE", "sliding"),
    "max_attempts": int(os.getenv("CYTOCV_RATE_LIMIT_MAX", "15")),
    "window_seconds": int(os.getenv("CYTOCV_RATE_LIMIT_WINDOW", "60")),
    "lockout_schedule": [60, 180, 300, 600, 1800, 3600],
}
SECURITY_HEADERS_ENABLED = True
SECURITY_PERMISSIONS_POLICY = "geolocation=(), microphone=(), camera=()"

# Cookie policy
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False  # Some JS reads the CSRF cookie directly.

# Browser security headers
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"

if SECURITY_STRICT:
    if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS:
        raise RuntimeError(
            "SECURITY_STRICT requires explicit CYTOCV_ALLOWED_HOSTS without wildcards."
        )
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
else:
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    SECURE_HSTS_SECONDS = 0
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False

# Default segmentation parameters
DEFAULT_SEGMENT_CONFIG = {
    "kernel_size": 5,
    "kernel_deviation": 1,
    "red_line_width": 1,
    "arrested": "Metaphase Arrested",
}
