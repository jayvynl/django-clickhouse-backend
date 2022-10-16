from typing import Dict

from django.db.models.sql import query
from django.db.models.sql import subqueries

from clickhouse_backend.compat import dj4


def settings_to_str(settings_dict: Dict) -> str:
    string = ', '.join(f'{k}={v}' for k, v in settings_dict.items())
    if string:
        return 'SETTINGS ' + string
    return ''


class Query(query.Query):
    def __init__(self, model, where=query.WhereNode, alias_cols=True):
        if dj4:
            super().__init__(model, alias_cols)
        else:
            super().__init__(model, where, alias_cols)
        self.settings = {}

    def clone(self):
        obj = super().clone()
        obj.settings = self.settings.copy()
        return obj

    def get_settings(self):
        return settings_to_str(self.settings)


for query_class in [subqueries.UpdateQuery, subqueries.DeleteQuery]:
    for attr in ['clone', 'get_settings']:
        setattr(query_class, attr, getattr(Query, attr))
