from django.db import models
from django.db.migrations import state
from django.db.models import options

from .query import QuerySet
from .sql import Query

# WHY THIS PATCH EXISTS:
# Django's ModelState.from_model() iterates DEFAULT_NAMES to capture Meta options
# into migration files (state.py line ~835). Without "engine" and "cluster" in this
# tuple, makemigrations silently drops these options — migrations would create tables
# with wrong engines. Django provides no backend-specific hook for custom Meta options.
# Both options.DEFAULT_NAMES and state.DEFAULT_NAMES must be patched because:
# - options.DEFAULT_NAMES: used by Options.__init__() to populate original_attrs
# - state.DEFAULT_NAMES: used by ModelState.from_model() to serialize into migrations
_CLICKHOUSE_META_OPTIONS = ("engine", "cluster")
if "engine" not in options.DEFAULT_NAMES:
    options.DEFAULT_NAMES = (*options.DEFAULT_NAMES, *_CLICKHOUSE_META_OPTIONS)
    state.DEFAULT_NAMES = options.DEFAULT_NAMES


class ClickhouseManager(models.Manager):
    _queryset_class = QuerySet

    def get_queryset(self):
        return self._queryset_class(
            model=self.model, query=Query(self.model), using=self._db, hints=self._hints
        )

    def settings(self, **kwargs):
        return self.get_queryset().settings(**kwargs)

    def prewhere(self, *args, **kwargs):
        return self.get_queryset().prewhere(*args, **kwargs)

    def datetimes(self, *args, **kwargs):
        return self.get_queryset().datetimes(*args, **kwargs)


class ClickhouseModel(models.Model):
    objects = ClickhouseManager()
    _overwrite_base_manager = ClickhouseManager()

    class Meta:
        abstract = True
        base_manager_name = "_overwrite_base_manager"

    def _do_update(
        self,
        base_qs,
        using,
        pk_val,
        values,
        update_fields,
        forced_update,
        returning_fields,
    ):
        filtered = base_qs.filter(pk=pk_val)
        if not values:
            if update_fields is not None or filtered.exists():
                return [()]
            return []
        return filtered._update(values, returning_fields)
