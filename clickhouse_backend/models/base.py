from django.db import models
from django.db.migrations import state
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

    # def delete(self, using=None, keep_parents=False):
    #     """
    #     When execute DELETE and UPDATE query. Clickhouse does not support
    #     "table"."column" in WHERE clause.
    #
    #     Clickhouse does not support Model inheritance or ForeignKey, so no
    #     complicated checking is needed. Simple deletion is faster.
    #     And Clickhouse can't return deleted rowcount, Cursor.rowcount is -1.
    #     """
    #     if self.pk is None:
    #         raise ValueError(
    #             "%s object can't be deleted because its %s attribute is set "
    #             "to None." % (self._meta.object_name, self._meta.pk.attname)
    #         )
    #     self.__class__._base_manager.filter(pk=self.pk).delete()
    #     setattr(self, self._meta.pk.attname, None)
    #     return 1, {self._meta.label: 1}
    #
    # delete.alters_data = True

    def _do_update(self, base_qs, using, pk_val, values, update_fields, forced_update):
        """
        Try to update the model. Return True if the model was updated (if an
        update query was done and a matching row was found in the DB).
        """
        filtered = base_qs.filter(pk=pk_val)
        if not values:
            # We can end up here when a model with just PK - in that case check that the PK still exists.
            return filtered.exists()
        return (
            filtered.exists() and
            # Clickhouse can not return updated rowcount, Cursor.rowcount is -1.
            (filtered._update(values) > 0 or filtered.exists())
        )
