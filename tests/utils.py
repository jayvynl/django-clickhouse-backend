from contextlib import contextmanager

from django.db import connection
from django.test.utils import isolate_apps

from clickhouse_backend import models


@contextmanager
def json_model(label, db_table=None, **kwargs):
    """A model holding one JSON column, created only for the test using it.

    Not a model of a test app: the JSON type is unusable before ClickHouse 25.3
    without a setting tests/settings.py cannot enable for every version it tests,
    and a model of an app is created for every test of the suite.
    """
    meta = {"app_label": label}
    if db_table:
        meta["db_table"] = db_table
    with isolate_apps(label):
        model = type(
            "JSONModel",
            (models.ClickhouseModel,),
            {
                "__module__": "%s.models" % label,
                "json": models.JSONField(**kwargs),
                "Meta": type("Meta", (), meta),
            },
        )
        with connection.schema_editor() as editor:
            editor.create_model(model)
        try:
            yield model
        finally:
            with connection.schema_editor() as editor:
                editor.delete_model(model)
