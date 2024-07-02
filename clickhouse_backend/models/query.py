from django.db.models import Q, query

from clickhouse_backend.models import sql


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
        if isinstance(clone.query, sql.Query):
            clone.query.setting_info.update(kwargs)
        return clone

    def prewhere(self, *args, **kwargs):
        """
        Return a new QuerySet instance with the args ANDed to the existing
        prewhere set.
        """
        self._not_support_combined_queries("prewhere")
        if (args or kwargs) and self.query.is_sliced:
            raise TypeError("Cannot prewhere a query once a slice has been taken.")
        clone = self._chain()
        clone._query.add_prewhere(Q(*args, **kwargs))
        return clone
