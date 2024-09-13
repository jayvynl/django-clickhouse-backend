from pathlib import Path

BASE_DIR = Path(__file__).parent
SECRET_KEY = "fake-key"
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.messages",
    "clickhouse_backend",
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
                "mutations_sync": 2,
                "insert_distributed_sync": 1,
                "insert_quorum": 2,
                "alter_sync": 2,
                "allow_suspicious_low_cardinality_types": 1,
                "allow_experimental_object_type": 1,
                "allow_experimental_json_type": 1,
            },
        },
        "TEST": {"cluster": "cluster"},
    },
    "s1r2": {
        "ENGINE": "clickhouse_backend.backend",
        "PORT": 9001,
        "OPTIONS": {
            "migration_cluster": "cluster",
            "connections_min": 1,
            "settings": {
                "mutations_sync": 2,
                "insert_distributed_sync": 1,
                "insert_quorum": 2,
                "alter_sync": 2,
                "allow_suspicious_low_cardinality_types": 1,
                "allow_experimental_object_type": 1,
                "allow_experimental_json_type": 1,
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
                "mutations_sync": 2,
                "insert_distributed_sync": 1,
                "insert_quorum": 2,
                "alter_sync": 2,
                "allow_suspicious_low_cardinality_types": 1,
                "allow_experimental_object_type": 1,
                "allow_experimental_json_type": 1,
            },
        },
        "TEST": {"cluster": "cluster", "managed": False},
    },
    "other": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    },
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
DATABASE_ROUTERS = ["dbrouters.ClickHouseRouter"]
MIGRATE = False
USE_TZ = False
