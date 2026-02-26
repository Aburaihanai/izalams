import os
from pathlib import Path
from dotenv import load_dotenv
from django.urls import reverse_lazy

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env file
load_dotenv(BASE_DIR / '.env')

from django.utils.translation import gettext_lazy as _

LANGUAGE_CODE = 'en-us'

LANGUAGES = [
    ('en', _('English')),
    ('ha', _('Hausa')),
    ('ar', _('Arabic')),
    ('fr', _('French')),
    ('yo', _('Yoruba')),
    ('ig', _('Igbo')),
]

LOCALE_PATHS = [
    BASE_DIR / 'locale/',
]
USE_I18N = True
USE_L10N = True

# --- SECURITY SETTINGS ---
SECRET_KEY = os.getenv('SECRET_KEY')
DEBUG = os.getenv('DEBUG') == 'True'
ALLOWED_HOSTS = ['Aburaihanai.pythonanywhere.com']

# --- APPLICATION DEFINITION ---
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'accounts',
    'donations',
    'axes',
]

AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesBackend',
    'django.contrib.auth.backends.ModelBackend',
]

# Configure the lockout behavior
AXES_FAILURE_LIMIT = 5
AXES_LOCKOUT_CALLABLE = None
AXES_LOCKOUT_URL = reverse_lazy('password_reset')  # Redirect here after 5 fails
AXES_RESET_ON_SUCCESS = True
AXES_COOLOFF_TIME = 0.05  # Time in hours
AXES_STRATEGY = 'axes.strategies.UsernameStrategy'
AXES_IP_LOOKUP_PARAMETERS = ['HTTP_X_FORWARDED_FOR']
AXES_LOCKOUT_PARAMETERS = ['username', 'ip_address']

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware', # For static files on Hostinger
    'django.contrib.sessions.middleware.SessionMiddleware', # REQUIRED for Admin/Login
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'axes.middleware.AxesMiddleware'
]

ROOT_URLCONF = 'izalams.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
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

WSGI_APPLICATION = 'izalams.wsgi.application'

# --- DATABASE ---
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# --- AUTHENTICATION & REDIRECTS ---
# This fixes your redirection issues
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'landing'
LOGIN_URL = 'login'
PASSWORD_RESET_COMPLETE_URL = 'login'

# --- PASSWORD VALIDATION ---
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# --- INTERNATIONALIZATION ---
TIME_ZONE = 'Africa/Lagos' # Correct for Nigeria
USE_TZ = True

# --- STATIC & MEDIA FILES ---
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

# This handles your Image Gallery and TikTok Videos
MEDIA_URL = '/media/'
MEDIA_ROOT = '/home/Aburaihanai/izalams/izalams/media'



DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --- EMAIL CONFIGURATION (For Approvals) ---
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend' # Shows emails in terminal for now


ROOT_URLCONF = 'izalams.urls'
AUTH_USER_MODEL = 'accounts.User'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
MEDIA_ROOT = BASE_DIR / 'media'

# Email Settings
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER

# Use the variables


# Paystack
PAYSTACK_SECRET_KEY = os.getenv('PAYSTACK_SECRET_KEY')
PAYSTACK_PUBLIC_KEY = os.getenv('PAYSTACK_PUBLIC_KEY')

# Email
