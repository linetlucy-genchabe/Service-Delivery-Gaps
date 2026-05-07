"""
CHA Dashboard – Django Settings
Supports local development (.env) and Railway production (environment variables)
"""
import os
import dj_database_url
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv('SECRET_KEY', 'change-me-in-production')
DEBUG = os.getenv('DEBUG', 'False') == 'True'

ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

# Allow Railway's generated domain automatically
RAILWAY_STATIC_URL = os.getenv('RAILWAY_STATIC_URL', '')
if RAILWAY_STATIC_URL:
    ALLOWED_HOSTS.append(RAILWAY_STATIC_URL)

# Also allow any .railway.app domain
ALLOWED_HOSTS.append('.railway.app')

INSTALLED_APPS = [
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'whitenoise.runserver_nostatic',
    'django.contrib.staticfiles',
    'dashboard',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'cha_dashboard.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'cha_dashboard.wsgi.application'

# ---------------------------------------------------------------------------
# Database — uses DATABASE_URL on Railway, falls back to local .env settings
# ---------------------------------------------------------------------------
DATABASE_URL = os.getenv('DATABASE_URL')

if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.parse(DATABASE_URL, conn_max_age=600)
    }
else:
    DATABASES = {
        'default': {
            'ENGINE':   'django.db.backends.postgresql',
            'NAME':     os.getenv('DB_NAME',     'cha_dashboard'),
            'USER':     os.getenv('DB_USER',     'postgres'),
            'PASSWORD': os.getenv('DB_PASSWORD', 'postgres'),
            'HOST':     os.getenv('DB_HOST',     'localhost'),
            'PORT':     os.getenv('DB_PORT',     '5432'),
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Nairobi'
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static files — WhiteNoise serves them in production
# ---------------------------------------------------------------------------
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'

DATA_UPLOAD_MAX_MEMORY_SIZE = 52428800
FILE_UPLOAD_MAX_MEMORY_SIZE = 52428800

# ---------------------------------------------------------------------------
# Security — enforced in production
# ---------------------------------------------------------------------------
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# ---------------------------------------------------------------------------
# Jazzmin Admin UI
# ---------------------------------------------------------------------------
JAZZMIN_SETTINGS = {
    "site_title": "SD Gaps Admin",
    "site_header": "Service Delivery Gaps",
    "site_brand": "Living Goods",
    "site_logo": "dashboard/lg_logo.png",
    "site_logo_classes": "img-circle",
    "site_icon": "dashboard/lg_logo.png",
    "welcome_sign": "Service Delivery Gaps Dashboard — Admin",
    "copyright": "© 2026 Linetlucy Genchabe",
    "search_model": ["auth.User", "dashboard.UploadBatch"],
    "topmenu_links": [
        {"name": "Dashboard", "url": "/", "new_window": False},
        {"name": "Upload Data", "url": "/upload/", "new_window": False},
        {"model": "auth.User"},
    ],
    "usermenu_links": [
        {"name": "View Dashboard", "url": "/", "new_window": False},
    ],
    "show_sidebar": True,
    "navigation_expanded": True,
    "icons": {
        "auth":                        "fas fa-users-cog",
        "auth.user":                   "fas fa-user",
        "auth.Group":                  "fas fa-users",
        "dashboard.UploadBatch":       "fas fa-upload",
        "dashboard.CHWRecord":         "fas fa-heartbeat",
        "dashboard.SupervisionRecord": "fas fa-clipboard-check",
    },
    "default_icon_parents": "fas fa-chevron-circle-right",
    "default_icon_children": "fas fa-circle",
    "related_modal_active": True,
    "show_ui_builder": False,
    "changeform_format": "horizontal_tabs",
    "language_chooser": False,
}

JAZZMIN_UI_TWEAKS = {
    "navbar_fixed": True,
    "footer_fixed": True,
    "sidebar_fixed": True,
    "sidebar": "sidebar-dark-primary",
    "navbar": "navbar-dark",
    "brand_colour": "navbar-dark",
    "theme": "default",
}