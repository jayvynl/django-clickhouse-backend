SECRET_KEY = "fake-key"
INSTALLED_APPS = []
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
