"""Django settings for Yeast-Web."""

from pathlib import Path
import os

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent


def _load_env_file(path: Path) -> None:
    """Load simple KEY=VALUE pairs from a .env file without overriding os.environ."""
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or key in os.environ:
            continue
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        os.environ[key] = value


_load_env_file(PROJECT_ROOT / ".env")
_load_env_file(BASE_DIR / ".env")

# Media storage
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Core settings (override in production)
SECRET_KEY = 'django-insecure-r_afs-3hujl8xfiqc%l#t*%$(bs*@ycdlnz$okl%i57g!tn%3y'
DEBUG = True
ALLOWED_HOSTS = []

# Authentication
AUTH_USER_MODEL = 'accounts.CustomUser'

AUTHENTICATION_BACKENDS = [
    # Email-based authentication
    'accounts.backends.EmailBackend',

    # Allauth auth methods (email/social)
    'allauth.account.auth_backends.AuthenticationBackend',
    #'django_auth_adfs.backend.AdfsAccessTokenBackend',
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
ROOT_URLCONF = 'yeastweb.urls'

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
WSGI_APPLICATION = 'yeastweb.wsgi.application'


# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
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

# Social auth providers
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        # For each OAuth based provider, either add a ``SocialApp``
        # (``socialaccount`` app) containing the required client
        # credentials, or list them here:
        'APP': {
            # TODO: Move client secrets to environment variables
            'client_id': '225323565107-ofofsr4m2hta51gmm68ocrtukh1jou83.apps.googleusercontent.com',
            'secret': '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',
            'key': ''
        },
        'SCOPE': ['profile', 'email']
    },
    "microsoft": {
        "APPS": [
            {
                "client_id": "7d0d357b-f8a4-41a7-8e9f-002504bd9b1c",
                "secret": "Fw.8Q~cetTJeJ3vqSmNsVdSjA1EcoXqL5Y2z3aBT",
                "settings": {
                    "tenant": "organizations",
                    "login_url": "https://login.microsoftonline.com",
                },
                'OAUTH_PKCE_ENABLED': True,
            }
        ],
    }
}

# OAuth provider redirects
SOCIALACCOUNT_LOGIN_ON_GET = False

# Microsoft ADFS (legacy / optional)
AUTH_ADFS = {
    'AUDIENCE': "7d0d357b-f8a4-41a7-8e9f-002504bd9b1c",
    'CLIENT_ID': "7d0d357b-f8a4-41a7-8e9f-002504bd9b1c",
    'CLIENT_SECRET': "91673088-079a-4bc0-a7de-348e3a0f0752",
    'CLAIM_MAPPING': {'first_name': 'given_name',
                      'last_name': 'family_name',
                      'email': 'upn'},
    'GROUPS_CLAIM': 'roles',
    'MIRROR_GROUPS': True,
    'USERNAME_CLAIM': 'upn',
    'TENANT_ID': "f6b6dd5b-f02f-441a-99a0-162ac5060bd2",
    'RELYING_PARTY_ID': "7d0d357b-f8a4-41a7-8e9f-002504bd9b1c",
}

# Allauth account configuration for email-only authentication.
ACCOUNT_USER_MODEL_EMAIL_FIELD = 'email'
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]

LOGIN_URL = "signin"
LOGIN_REDIRECT_URL = "profile"

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
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.getenv("YEASTWEB_EMAIL_HOST", "smtp.gmail.com")
EMAIL_HOST_USER = os.getenv("YEASTWEB_EMAIL_HOST_USER", "yeastanalysistool@gmail.com")
EMAIL_HOST_PASSWORD = os.getenv("YEASTWEB_EMAIL_HOST_PASSWORD", "drjx oiir ejnx lwdn")  # TODO: Change before production
EMAIL_PORT = 587
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = os.getenv("YEASTWEB_DEFAULT_FROM_EMAIL", "no-reply@noreply.x.edu")
EMAIL_REPLY_TO = os.getenv("YEASTWEB_EMAIL_REPLY_TO", "no-reply@noreply.x.edu")

# Google reCAPTCHA
RECAPTCHA_ENABLED = os.getenv("CYTOCV_RECAPTCHA_ENABLED", "0") == "1"
RECAPTCHA_SITE_KEY = os.getenv("CYTOCV_RECAPTCHA_SITE_KEY", "")
RECAPTCHA_SECRET_KEY = os.getenv("CYTOCV_RECAPTCHA_SECRET_KEY", "")
RECAPTCHA_VERIFY_URL = os.getenv(
    "CYTOCV_RECAPTCHA_VERIFY_URL",
    "https://www.google.com/recaptcha/api/siteverify",
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

# Security profile toggles (defaults to not DEBUG; override with YEASTWEB_SECURITY_STRICT)
_security_strict_env = os.getenv("YEASTWEB_SECURITY_STRICT")
if _security_strict_env is None or _security_strict_env.strip() == "":
    SECURITY_STRICT = not DEBUG
else:
    SECURITY_STRICT = _security_strict_env.strip().lower() in ("1", "true", "yes", "on")
SECURITY_RATE_LIMIT_ENABLED = os.getenv("YEASTWEB_RATE_LIMIT_ENABLED", "1") == "1"
SECURITY_RATE_LIMIT = {
    "mode": os.getenv("YEASTWEB_RATE_LIMIT_MODE", "sliding"),
    "max_attempts": int(os.getenv("YEASTWEB_RATE_LIMIT_MAX", "15")),
    "window_seconds": int(os.getenv("YEASTWEB_RATE_LIMIT_WINDOW", "60")),
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
    "mCherry_line_width": 1,
    "arrested": "Metaphase Arrested",
}
