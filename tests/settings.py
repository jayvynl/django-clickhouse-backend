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
            "migration_cluster": "cluster",
            "connections_min": 1,
            "settings": {
                "mutations_sync": 1,
                "allow_suspicious_low_cardinality_types": 1,
                "allow_experimental_object_type": 1,
                "insert_distributed_sync": 1,
            },
        },
        "TEST": {"cluster": "cluster"},
    },
    "other": {
        "ENGINE": "clickhouse_backend.backend",
        "NAME": "other",
        "OPTIONS": {
            "connections_min": 1,
            "settings": {
                "mutations_sync": 1,
                "allow_suspicious_low_cardinality_types": 1,
                "allow_experimental_object_type": 1,
                "insert_distributed_sync": 1,
            },
        },
    },
    "s1r2": {
        "ENGINE": "clickhouse_backend.backend",
        "PORT": 9001,
        "OPTIONS": {
            "migration_cluster": "cluster",
            "connections_min": 1,
            "settings": {
                "mutations_sync": 1,
                "allow_suspicious_low_cardinality_types": 1,
                "allow_experimental_object_type": 1,
                "insert_distributed_sync": 1,
            },
        },
        "TEST": {"cluster": "cluster", "managed": False},
    },
    "s2r1": {
        "ENGINE": "clickhouse_backend.backend",
        "PORT": 9002,
        "OPTIONS": {
            "migration_cluster": "cluster",
            "connections_min": 1,
            "settings": {
                "mutations_sync": 1,
                "allow_suspicious_low_cardinality_types": 1,
                "allow_experimental_object_type": 1,
                "insert_distributed_sync": 1,
            },
        },
        "TEST": {"cluster": "cluster", "managed": False},
    },
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
MIGRATE = False
