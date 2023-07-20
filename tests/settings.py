SECRET_KEY = "fake-key"
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.messages",
]
MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]
DATABASES = {
    "default": {
        "ENGINE": "clickhouse_backend.backend",
        "OPTIONS": {
            "settings": {
                "mutations_sync": 1,
                "allow_suspicious_low_cardinality_types": 1,
                "allow_experimental_object_type": 1,
            }
        }
    },
    "other": {
        "ENGINE": "clickhouse_backend.backend",
        "NAME": "other",
        "OPTIONS": {
            "settings": {
                "mutations_sync": 1,
                "allow_suspicious_low_cardinality_types": 1,
                "allow_experimental_object_type": 1,
            }
        }
    }
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
MIGRATE = False
