SECRET_KEY = 'fake-key'
INSTALLED_APPS = [
    'django.contrib.contenttypes',
]
DATABASES = {
    'default': {
        'ENGINE': 'clickhouse_backend.backend',
        'NAME': 'test',
        'OPTIONS': {
            'settings': {
                'mutations_sync': 1,
            }
        }
    }
}
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
MIGRATE = False
