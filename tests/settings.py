SECRET_KEY = 'fake-key'
INSTALLED_APPS = []
DATABASES = {
    'default': {
        'ENGINE': 'clickhouse_backend.backend',
        'NAME': 'default',
        'OPTIONS': {
            'settings': {
                'mutations_sync': 1,
            }
        }
    },
    'other': {
        'ENGINE': 'clickhouse_backend.backend',
        'NAME': 'other',
        'OPTIONS': {
            'settings': {
                'mutations_sync': 1,
            }
        }
    }
}
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
MIGRATE = False
