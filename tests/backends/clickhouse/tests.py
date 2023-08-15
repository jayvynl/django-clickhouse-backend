from unittest import mock

from django.core.exceptions import ImproperlyConfigured
from django.db import (
    DatabaseError,
    connection,
)
from django.test import TestCase

from clickhouse_backend.backend.base import DatabaseWrapper
from clickhouse_backend.backend.operations import DatabaseOperations


class Tests(TestCase):
    databases = {"default", "other"}

    def test_nodb_cursor(self):
        """
        The _nodb_cursor() fallbacks to the default connection database.
        """
        with connection._nodb_cursor() as cursor:
            self.assertIs(cursor.closed, False)
            self.assertIsNotNone(cursor.db.connection)
        self.assertIs(cursor.closed, True)
        self.assertIsNone(cursor.db.connection)

    def test_nodb_cursor_reraise_exceptions(self):
        with self.assertRaisesMessage(DatabaseError, "exception"):
            with connection._nodb_cursor():
                raise DatabaseError("exception")

    def test_database_name_too_long(self):
        settings = connection.settings_dict.copy()
        max_name_length = connection.ops.max_name_length()
        settings["NAME"] = "a" + (max_name_length * "a")
        msg = (
            "The database name '%s' (%d characters) is longer than "
            "Clickhouse's limit of %s characters. Supply a shorter NAME in "
            "settings.DATABASES."
        ) % (settings["NAME"], max_name_length + 1, max_name_length)
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            DatabaseWrapper(settings).get_connection_params()

    def test_clickhouse_settings(self):
        settings = connection.settings_dict.copy()
        settings["OPTIONS"] = {"settings": {"mutations_sync": 1}}
        settings["NAME"] = ""
        params = DatabaseWrapper(settings).get_connection_params()
        self.assertEqual(params["settings"], {"mutations_sync": 1})

    def test_connect_no_is_usable_checks(self):
        new_connection = connection.copy()
        try:
            with mock.patch.object(new_connection, "is_usable") as is_usable:
                new_connection.connect()
            is_usable.assert_not_called()
        finally:
            new_connection.close()

    def _select(self, val):
        with connection.cursor() as cursor:
            cursor.execute("SELECT %s", (val,))
            return cursor.fetchone()[0]

    def test_select_ascii_array(self):
        a = ["awef"]
        b = self._select(a)
        self.assertEqual(a[0], b[0])

    def test_select_unicode_array(self):
        a = ["ᄲawef"]
        b = self._select(a)
        self.assertEqual(a[0], b[0])

    def test_lookup_cast(self):
        do = DatabaseOperations(connection=None)
        lookups = (
            "iexact",
            "contains",
            "icontains",
            "startswith",
            "istartswith",
            "endswith",
            "iendswith",
            "regex",
            "iregex",
        )
        for lookup in lookups:
            with self.subTest(lookup=lookup):
                self.assertIn("Nullable(String)", do.lookup_cast(lookup))

    def test_get_database_version(self):
        new_connection = connection.copy()
        new_connection.ch_version = "22.9.3.18"
        self.assertEqual(new_connection.get_database_version(), (22, 9, 3, 18))
