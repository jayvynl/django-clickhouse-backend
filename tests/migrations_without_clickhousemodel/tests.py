from django.core.management import call_command
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder
from django.test import TestCase


class TestMigrationTable(TestCase):
    # Regression test for https://github.com/jayvynl/django-clickhouse-backend/issues/51
    def test_update_from_110(self):
        with connection.cursor() as cursor:
            cursor.execute("ALTER table django_migrations DROP COLUMN deleted")
            call_command("migrate", fake=True)
            fields = connection.introspection.get_table_description(
                cursor, "django_migrations"
            )
            self.assertIn("deleted", {field.name for field in fields})

    def test_has_table(self):
        recorder = MigrationRecorder(connection)

        with connection.cursor() as cursor:
            cursor.execute("ALTER table django_migrations DROP COLUMN deleted")
            # One query for tables, second one for the check, the third query to add deleted column.
            with self.assertNumQueries(3):
                recorder.has_table()

            fields = connection.introspection.get_table_description(
                cursor, "django_migrations"
            )
            self.assertIn("deleted", {field.name for field in fields})

            # invalidate cache
            recorder._has_table = False

            # now only two queries - one for tables, second one for the check.
            with self.assertNumQueries(2):
                recorder.has_table()

            # results are cached
            with self.assertNumQueries(0):
                recorder.has_table()
