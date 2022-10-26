from django.db.models import query

from .sql import Query


class QuerySet(query.QuerySet):
    def explain(self, *, format=None, type=None, **settings):
        """
        Runs an EXPLAIN on the SQL query this QuerySet would perform, and
        returns the results.
        https://clickhouse.com/docs/en/sql-reference/statements/explain/
        """
        return self.query.explain(using=self.db, format=format, type=type, **settings)

    def settings(self, **kwargs):
        clone = self._chain()
        if isinstance(clone.query, Query):
            clone.query.setting_info.update(kwargs)
        return clone
