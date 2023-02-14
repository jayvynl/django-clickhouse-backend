from .models import Foo
from django.test import SimpleTestCase
from clickhouse_backend import models
from django.db import connection


class BasicFieldTests(SimpleTestCase):
    def test_deconstruct(self):
        field = models.Int8Field(
            unique=True,
            db_index=True,
            unique_for_data=True,
            unique_for_month=True,
            unique_for_year=True,
            db_tablespace="a",
            db_collation="C"
        )
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "clickhouse_backend.models.Int8Field")
        for key in [
            "unique",
            "db_index",
            "unique_for_date",
            "unique_for_month",
            "unique_for_year",
            "db_tablespace",
            "db_collation",
        ]:
            self.assertNotIn(key, kwargs)

    def test_deconstruct_low_cardinality(self):
        field = models.Int8Field(low_cardinality=False)
        name, path, args, kwargs = field.deconstruct()
        self.assertNotIn("low_cardinality", kwargs)

        field = models.Int8Field(low_cardinality=True)
        name, path, args, kwargs = field.deconstruct()
        self.assertIn("low_cardinality", kwargs)

    def test_db_type(self):
        field = models.Int8Field()
        self.assertEqual(field.db_type(connection), "Int8")
        field = models.Int8Field(null=True)
        self.assertEqual(field.db_type(connection), "Nullable(Int8)")
        field = models.Int8Field(low_cardinality=True)
        self.assertEqual(field.db_type(connection), "LowCardinality(Int8)")
        field = models.Int8Field(null=True, low_cardinality=True)
        self.assertEqual(field.db_type(connection), "LowCardinality(Nullable(Int8))")
