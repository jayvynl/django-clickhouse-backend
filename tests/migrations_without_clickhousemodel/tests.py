from django.core.management import call_command
from django.db import connection
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
