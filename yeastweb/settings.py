from pathlib import Path
import os
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential

load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
WSGI_APPLICATION = "yeastweb.wsgi.application"
# Media files directory
MEDIA_URL = f"https://{os.getenv('AZ_STORAGE_NAME')}/media"
MEDIA_ROOT = None

# Quick-start development settings - unsuitable for production
SECRET_KEY = os.getenv("SECRET_KEY")
DEBUG = True


ALLOWED_HOSTS = [os.getenv("WEBSITE_HOSTNAME"), "localhost", "127.0.0.1"]


# Custom User with unique uuid
AUTH_USER_MODEL = "accounts.CustomUser"

AUTHENTICATION_BACKENDS = [
    # Needed to login by username in Django admin, regardless of `allauth`
    "django.contrib.auth.backends.ModelBackend",
    # `allauth` specific authentication methods, such as login by email
    "allauth.account.auth_backends.AuthenticationBackend",
    # for microsoft
    #'django_auth_adfs.backend.AdfsAccessTokenBackend',
]

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "django_tables2",
    "core",
    "accounts",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "allauth.socialaccount.providers.microsoft",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": BASE_DIR / "cache",
    },
    # "default": {
    #    "BACKEND": "django.core.cache.backends.memcached.PyMemcacheCache",
    #    "LOCATION": "127.0.0.1:11211",
    # }
}

ROOT_URLCONF = "yeastweb.urls"

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
                "django.template.context_processors.media",  # This adds MEDIA_URL to all templates
                "django.template.context_processors.request",
            ],
        },
    },
]


WSGI_APPLICATION = "yeastweb.wsgi.application"


# Database
DATABASES = {
    "default": {
        # PostgreSQL
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DBNAME"),
        "HOST": os.getenv("DBHOST"),
        "USER": os.getenv("DBUSER"),
        "PASSWORD": os.getenv("DBPASS"),
        "PORT": os.getenv("DBPORT", "5432"),
    }
}

# Storage
STORAGES = {
    "default": {
        "BACKEND": "storages.backends.azure_storage.AzureStorage",
        "OPTIONS": {
            "token_credential": DefaultAzureCredential(),
            "account_name": "yeastimagestorage",
            "azure_container": "media",
        },
    },
    "staticfiles": {
        "BACKEND": "storages.backends.azure_storage.AzureStorage",
        "OPTIONS": {
            "token_credential": DefaultAzureCredential(),
            "account_name": "yeastimagestorage",
            "azure_container": "static",
        },
    },
}
# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# For account with different provider
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        # For each OAuth based provider, either add a ``SocialApp``
        # (``socialaccount`` app) containing the required client
        # credentials, or list them here:
        "APP": {
            # TODO: Hide these
            "client_id": os.getenv("GOOGLE_CLIENT"),
            "secret": os.getenv("GOOGLE_SECRET"),
            "key": "",
        },
        "SCOPE": ["profile", "email"],
    },
    "microsoft": {
        "APPS": [
            {
                "client_id": os.getenv("MSFT_CLIENT"),
                "secret": os.getenv("MSFT_SECRET"),
                "settings": {
                    "tenant": "organizations",
                    "login_url": "https://login.microsoftonline.com",
                },
                "OAUTH_PKCE_ENABLED": True,
                "redirect_uri": f"https://{os.getenv('WEBSITE_HOSTNAME')}/login/oauthmicrosoft/login/callback/",
            }
        ],
    },
}

# for microsoft login
AUTH_ADFS = {
    "AUDIENCE": os.getenv("MSFT_CLIENT"),
    "CLIENT_ID": os.getenv("MSFT_CLIENT"),
    "CLIENT_SECRET": os.getenv("MSFT_CLIENT_SECRET"),
    "CLAIM_MAPPING": {
        "first_name": "given_name",
        "last_name": "family_name",
        "email": "upn",
    },
    "GROUPS_CLAIM": "roles",
    "MIRROR_GROUPS": True,
    "USERNAME_CLAIM": "upn",
    "TENANT_ID": os.getenv("MSFT_TENANT_ID"),
    "RELYING_PARTY_ID": os.getenv("MSFT_CLIENT"),
}

ACCOUNT_USER_MODEL_EMAIL_FIELD = "email"

LOGIN_REDIRECT_URL = "profile"

# Security
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
CSRF_TRUSTED_ORIGINS = [os.getenv("WEBSITE_HOSTNAME"), "localhost"]

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
SITE_ID = 1

# Static files (CSS, JavaScript, Images)
STATIC_URL = "static/"

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Email setting
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.gmail.com"
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")
EMAIL_PORT = 587
EMAIL_USE_TLS = True

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
