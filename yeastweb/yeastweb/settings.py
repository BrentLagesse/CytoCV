from pathlib import Path
import os

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Media files directory
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Quick-start development settings - unsuitable for production
SECRET_KEY = 'django-insecure-r_afs-3hujl8xfiqc%l#t*%$(bs*@ycdlnz$okl%i57g!tn%3y'
DEBUG = True
ALLOWED_HOSTS = []

# Custom User with unique uuid
AUTH_USER_MODEL = 'accounts.CustomUser'

AUTHENTICATION_BACKENDS = [
    # Needed to login by username in Django admin, regardless of `allauth`
    'django.contrib.auth.backends.ModelBackend',

    # `allauth` specific authentication methods, such as login by email
    'allauth.account.auth_backends.AuthenticationBackend',
    # for microsoft
    #'django_auth_adfs.backend.AdfsAccessTokenBackend',
]

SOCIALACCOUNT_ADAPTER = "accounts.adapters.CustomSocialAccountAdapter"

# Application definition
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

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": BASE_DIR / 'cache',
    },

    #"default": {
    #    "BACKEND": "django.core.cache.backends.memcached.PyMemcacheCache",
    #    "LOCATION": "127.0.0.1:11211",
    #}

}

ROOT_URLCONF = 'yeastweb.urls'

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
                'django.template.context_processors.media',  # This adds MEDIA_URL to all templates
                'django.template.context_processors.request',
            ],
        },
    },
]


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

# For account with different provider
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        # For each OAuth based provider, either add a ``SocialApp``
        # (``socialaccount`` app) containing the required client
        # credentials, or list them here:
        'APP': {
            #TODO: Hide these
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

# for microsoft login

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

ACCOUNT_USER_MODEL_EMAIL_FIELD = 'email'

LOGIN_REDIRECT_URL = "profile"

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True
SITE_ID = 1
SOCIALACCOUNT_LOGIN_ON_GET = False

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Email setting
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_HOST_USER = 'yeastanalysistool@gmail.com'
EMAIL_HOST_PASSWORD = 'drjx oiir ejnx lwdn' # TODO: CHANGE when enter production
EMAIL_PORT = 587
EMAIL_USE_TLS = True

# Content Security Policy (CSP)
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'", "'unsafe-inline'", "https://cdn.jsdelivr.net")
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'", "https://fonts.googleapis.com")
CSP_IMG_SRC = ("'self'", "data:", "blob:")
CSP_FONT_SRC = ("'self'", "https://fonts.gstatic.com")
CSP_CONNECT_SRC = ("'self'",)
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

SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_HTTPONLY = True
# Keep False because some JS reads the CSRF cookie directly.
CSRF_COOKIE_HTTPONLY = False

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

DEFAULT_SEGMENT_CONFIG = {
    # odd integer for your Gaussian blur kernel
    "kernel_size": 5,
    # sigma for that blur
    "kernel_deviation": 1,
    # pixel-width of the mCherry “line” drawn for intensity
    "mCherry_line_width": 1,
    # must be either "Metaphase Arrested" or "G1 Arrested"
    "arrested": "Metaphase Arrested",
}
