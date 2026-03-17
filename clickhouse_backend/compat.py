import django
from django.db import models

dj_ge51 = django.VERSION >= (5, 1)
dj_ge52 = django.VERSION >= (5, 2)
dj_ge6 = django.VERSION >= (6,)


def db_table_comment(model):
    """Return a model's database table comment."""
    return model._meta.db_table_comment or ""


def field_db_comment(field):
    """Return a field's database column comment."""
    return field.db_comment or ""


def field_has_db_default(field):
    """Check if a field has database level default value."""
    if dj_ge52:
        return field.has_db_default()
    return field.db_default is not models.NOT_PROVIDED
