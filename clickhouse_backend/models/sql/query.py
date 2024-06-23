from collections import namedtuple

from django.db import router
from django.db.models.sql import query, subqueries
from django.db.models.sql.constants import INNER
from django.db.models.sql.where import AND

from clickhouse_backend import compat

ExplainInfo = namedtuple("ExplainInfo", ("format", "type", "options"))


class Query(query.Query):
    def __init__(self, model, where=query.WhereNode, alias_cols=True):
        if compat.dj_ge4:
            super().__init__(model, alias_cols)
        else:
            super().__init__(model, where, alias_cols)
        self.setting_info = {}
        self.prewhere = query.WhereNode()

    def sql_with_params(self):
        """Choose the right db when database router is used."""
        return self.get_compiler(router.db_for_read(self.model)).as_sql()

    def clone(self):
        obj = super().clone()
        obj.setting_info = self.setting_info.copy()
        return obj

    def explain(self, using, format=None, type=None, **settings):
        q = self.clone()
        q.explain_info = ExplainInfo(format, type, settings)
        compiler = q.get_compiler(using=using)
        return "\n".join(compiler.explain_query())

    def add_prewhere(self, q_object):
        """
        A preprocessor for the internal _add_q(). Responsible for doing final
        join promotion.
        """
        # For join promotion this case is doing an AND for the added q_object
        # and existing conditions. So, any existing inner join forces the join
        # type to remain inner. Existing outer joins can however be demoted.
        # (Consider case where rel_a is LOUTER and rel_a__col=1 is added - if
        # rel_a doesn't produce any rows, then the whole condition must fail.
        # So, demotion is OK.
        existing_inner = {
            a for a in self.alias_map if self.alias_map[a].join_type == INNER
        }
        clause, _ = self._add_q(q_object, self.used_aliases)
        if clause:
            self.prewhere.add(clause, AND)
        self.demote_joins(existing_inner)


def clone_decorator(cls):
    old_clone = cls.clone

    def clone(self):
        obj = old_clone(self)
        if hasattr(obj, "setting_info"):
            obj.setting_info = self.setting_info.copy()
        return obj

    cls.clone = clone
    return cls


clone_decorator(subqueries.UpdateQuery)
clone_decorator(subqueries.DeleteQuery)
