from django.db import models
from django.db.migrations import state
from django.db.models import functions
from django.db.models import options
from django.db.models.manager import BaseManager

from .query import QuerySet
from .sql import Query

options.DEFAULT_NAMES = (
    'verbose_name', 'verbose_name_plural', 'db_table', 'ordering',
    'unique_together', 'permissions', 'get_latest_by', 'order_with_respect_to',
    'app_label', 'db_tablespace', 'abstract', 'managed', 'proxy', 'swappable',
    'auto_created', 'index_together', 'apps', 'default_permissions',
    'select_on_save', 'default_related_name', 'required_db_features',
    'required_db_vendor', 'base_manager_name', 'default_manager_name',
    'indexes', 'constraints',
    # Clickhouse features
    'engine',
)
# Also monkey patch state.DEFAULT_NAMES, this makes new option names contained in migrations.
state.DEFAULT_NAMES = options.DEFAULT_NAMES


def as_clickhouse(self, compiler, connection, **extra_context):
    return functions.Random.as_sql(
        self, compiler, connection, function="rand64", **extra_context
    )


functions.Random.as_clickhouse = as_clickhouse


class ClickhouseManager(BaseManager.from_queryset(QuerySet)):
    def get_queryset(self):
        """
        User defined Query and QuerySet class that support clickhouse particular query.
        """
        return self._queryset_class(
            model=self.model,
            query=Query(self.model),
            using=self._db,
            hints=self._hints
        )


class ClickhouseModel(models.Model):
    objects = ClickhouseManager()

    class Meta:
        abstract = True

    def _do_update(self, base_qs, using, pk_val, values, update_fields, forced_update):
        """
         Try to update the model. Return True if the model was updated (if an
         update query was done and a matching row was found in the DB).
         """
        filtered = base_qs.filter(pk=pk_val)
        if not values:
            # We can end up here when saving a model in inheritance chain where
            # update_fields doesn't target any field in current model. In that
            # case we just say the update succeeded. Another case ending up here
            # is a model with just PK - in that case check that the PK still
            # exists.
            return update_fields is not None or filtered.exists()
        return (
                filtered.exists()
                and
                # It may happen that the object is deleted from the DB right after
                # this check, causing the subsequent UPDATE to return zero matching
                # rows. The same result can occur in some rare cases when the
                # database returns zero despite the UPDATE being executed
                # successfully (a row is matched and updated). In order to
                # distinguish these two cases, the object's existence in the
                # database is again checked for if the UPDATE query returns 0.
                (filtered._update(values) > 0 or filtered.exists())
        )
