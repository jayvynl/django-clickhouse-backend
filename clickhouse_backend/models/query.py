from django.db.models import query

from .sql import Query


class QuerySet(query.QuerySet):
    def settings(self, **kwargs):
        clone = self._chain()
        if isinstance(clone.query, Query):
            clone.query.settings.update(kwargs)
        return clone
