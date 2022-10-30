import sys

from clickhouse_driver.errors import ErrorCodes
from django.db.backends.base.creation import BaseDatabaseCreation
from django.db.backends.utils import strip_quotes


class DatabaseCreation(BaseDatabaseCreation):

    def _quote_name(self, name):
        return self.connection.ops.quote_name(name)

    def sql_table_creation_suffix(self):
        test_settings = self.connection.settings_dict["TEST"]
        engine = test_settings.get("ENGINE")
        if engine:
            return "ENGINE = %s" % engine
        return ""

    def _database_exists(self, cursor, database_name):
        cursor.execute(
            "SELECT 1 FROM system.databases WHERE name = %s",
            [strip_quotes(database_name)]
        )
        return cursor.fetchone() is not None

    def create_test_db(self, verbosity=1, autoclobber=False, serialize=True, keepdb=False):
        super().create_test_db(verbosity, autoclobber, serialize, keepdb)
        test_settings = self.connection.settings_dict["TEST"]
        if "fake_transaction" in test_settings:
            self.connection.fake_transaction = test_settings["fake_transaction"]

    def _execute_create_test_db(self, cursor, parameters, keepdb=False):
        try:
            if keepdb and self._database_exists(cursor, parameters["dbname"]):
                # If the database should be kept and it already exists, don't
                # try to create a new one.
                return
            super()._execute_create_test_db(cursor, parameters, keepdb)
        except Exception as e:
            if not e.args or getattr(e.args[0], "code", "") != ErrorCodes.DATABASE_ALREADY_EXISTS:
                # All errors except "database already exists" cancel tests.
                self.log("Got an error creating the test database: %s" % e)
                sys.exit(2)
            elif not keepdb:
                # If the database should be kept, ignore "database already
                # exists".
                raise
