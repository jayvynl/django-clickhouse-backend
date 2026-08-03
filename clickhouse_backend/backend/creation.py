import sys

from clickhouse_driver.errors import ErrorCodes
from django.core.management import call_command
from django.db.backends.base.creation import BaseDatabaseCreation
from django.db.backends.utils import strip_quotes
from django.conf import settings
from django.utils.module_loading import import_string


class DatabaseCreation(BaseDatabaseCreation):
    def _quote_name(self, name):
        return self.connection.ops.quote_name(name)

    def sql_table_creation_suffix(self):
        test_settings = self.connection.settings_dict["TEST"]
        cluster = test_settings.get("cluster")
        engine = test_settings.get("engine")

        parts = []
        if cluster:
            parts.append(f"ON CLUSTER {self.connection.ops.quote_name(cluster)}")
        if engine:
            parts.append(f"ENGINE = {engine}")
        return " ".join(parts)

    def _get_on_cluster(self):
        test_settings = self.connection.settings_dict["TEST"]
        cluster = test_settings.get("cluster")
        if cluster:
            return f"ON CLUSTER {self.connection.ops.quote_name(cluster)}"
        return ""

    def _database_exists(self, cursor, database_name):
        cursor.execute(
            "SELECT 1 FROM system.databases WHERE name = %s",
            [strip_quotes(database_name)],
        )
        return cursor.fetchone() is not None

    def create_test_db(
        self, verbosity=1, autoclobber=False, serialize=True, keepdb=False
    ):
        super().create_test_db(verbosity, autoclobber, serialize, keepdb)
        test_settings = self.connection.settings_dict["TEST"]
        if "fake_transaction" in test_settings:
            self.connection.fake_transaction = test_settings["fake_transaction"]
        self.mark_expected_failures_and_skips()

    def _create_test_db(self, verbosity, autoclobber, keepdb=False):
        """
        Internal implementation - create the test db tables.
        """
        if not self.connection.settings_dict["TEST"].get("managed", True):
            return
        test_database_name = self._get_test_db_name()
        test_db_params = {
            "dbname": self.connection.ops.quote_name(test_database_name),
            "suffix": self.sql_table_creation_suffix(),
        }
        # Create the test database and connect to it.
        with self._nodb_cursor() as cursor:
            try:
                self._execute_create_test_db(cursor, test_db_params, keepdb)
            except Exception as e:
                # if we want to keep the db, then no need to do any of the below,
                # just return and skip it all.
                if keepdb:
                    return test_database_name

                self.log("Got an error creating the test database: %s" % e)
                if not autoclobber:
                    confirm = input(
                        "Type 'yes' if you would like to try deleting the test "
                        "database '%s', or 'no' to cancel: " % test_database_name
                    )
                if autoclobber or confirm == "yes":
                    try:
                        if verbosity >= 1:
                            self.log(
                                "Destroying old test database for alias %s..."
                                % (
                                    self._get_database_display_str(
                                        verbosity, test_database_name
                                    ),
                                )
                            )
                        sql = "DROP DATABASE %(dbname)s" % test_db_params
                        on_cluster = self._get_on_cluster()
                        if on_cluster:
                            sql = f"{sql} {on_cluster} SYNC"
                        cursor.execute(sql)
                        self._execute_create_test_db(cursor, test_db_params, keepdb)
                    except Exception as e:
                        self.log("Got an error recreating the test database: %s" % e)
                        sys.exit(2)
                else:
                    self.log("Tests cancelled.")
                    sys.exit(1)

        return test_database_name

    def _execute_create_test_db(self, cursor, parameters, keepdb=False):
        try:
            if keepdb and self._database_exists(cursor, parameters["dbname"]):
                # If the database should be kept and it already exists, don't
                # try to create a new one.
                return
            super()._execute_create_test_db(cursor, parameters, keepdb)
        except Exception as e:
            if (
                not e.args
                or getattr(e.args[0], "code", "") != ErrorCodes.DATABASE_ALREADY_EXISTS
            ):
                # All errors except "database already exists" cancel tests.
                self.log("Got an error creating the test database: %s" % e)
                sys.exit(2)
            elif not keepdb:
                # If the database should be kept, ignore "database already
                # exists".
                raise

    def _destroy_test_db(self, test_database_name, verbosity):
        test_settings = self.connection.settings_dict["TEST"]
        if not test_settings.get("managed", True):
            return
        sql = "DROP DATABASE %s" % self.connection.ops.quote_name(test_database_name)
        on_cluster = self._get_on_cluster()
        if on_cluster:
            sql = f"{sql} {on_cluster} SYNC"
        with self._nodb_cursor() as cursor:
            cursor.execute(sql)

    def _clone_test_db(self, suffix, verbosity, keepdb=False):
        """
        Create a clone of the test database for a parallel worker.

        ClickHouse has no ``CREATE DATABASE ... AS <template>``. Copying each
        table's DDL is not viable either: ``SHOW CREATE TABLE`` bakes in the
        source database name, which would make ``Distributed`` engines that
        reference ``currentDatabase()`` point back at the source database, and
        ``Replicated`` engines that share a ZooKeeper path would collide. So the
        clone is populated by re-running migrations against it, reusing the exact
        table-creation code path (ON CLUSTER, ``{uuid}`` replica paths and
        ``currentDatabase()`` are all resolved for the clone database).

        Note: models pinned to a hardcoded ZooKeeper path (one that does not
        embed ``{uuid}`` or ``{database}``) cannot be cloned onto the same
        cluster because their replica path is not unique, so ``--parallel`` is
        unsupported for such models.
        """
        source_database_name = self.connection.settings_dict["NAME"]
        target_database_name = self.get_test_db_clone_settings(suffix)["NAME"]
        test_db_params = {
            "dbname": self.connection.ops.quote_name(target_database_name),
            "suffix": self.sql_table_creation_suffix(),
        }
        # An unmanaged alias must not CREATE DATABASE, another alias already did
        # so ON CLUSTER, but it must still migrate: tables that are not
        # ON CLUSTER only exist on the node the migration ran against. Same
        # split as create_test_db(), which also migrates unmanaged aliases.
        managed = self.connection.settings_dict["TEST"].get("managed", True)
        already_exists = False

        if managed:
            with self._nodb_cursor() as cursor:
                already_exists = keepdb and self._database_exists(
                    cursor, target_database_name
                )
                if not already_exists:
                    try:
                        self._execute_create_test_db(cursor, test_db_params, keepdb)
                    except Exception:
                        try:
                            if verbosity >= 1:
                                self.log(
                                    "Destroying old test database for alias %s..."
                                    % (
                                        self._get_database_display_str(
                                            verbosity, target_database_name
                                        ),
                                    )
                                )
                            sql = "DROP DATABASE %(dbname)s" % test_db_params
                            on_cluster = self._get_on_cluster()
                            if on_cluster:
                                sql = f"{sql} {on_cluster} SYNC"
                            cursor.execute(sql)
                            self._execute_create_test_db(cursor, test_db_params, keepdb)
                        except Exception as e:
                            self.log("Got an error cloning the test database: %s" % e)
                            sys.exit(2)

        # An existing clone that is being kept is assumed to already hold the
        # schema, mirroring how create_test_db() treats keepdb.
        if already_exists:
            return

        self._migrate_clone_schema(
            source_database_name, target_database_name, verbosity
        )

    def _migrate_clone_schema(
        self, source_database_name, target_database_name, verbosity
    ):
        """Reproduce the schema in the clone database by running migrations."""
        connection = self.connection
        connection.close()
        connection.settings_dict["NAME"] = target_database_name
        try:
            call_command(
                "migrate",
                verbosity=max(verbosity - 1, 0),
                interactive=False,
                database=connection.alias,
                run_syncdb=True,
            )
        finally:
            connection.settings_dict["NAME"] = source_database_name
            connection.close()

    def mark_expected_failures_and_skips(self):
        """
        Mark tests in Django's test suite which are expected failures on this
        database and test which should be skipped on this database.
        """
        # Only load unittest if we're actually testing.
        from unittest import expectedFailure, skip

        for test_name in self.connection.features.django_test_expected_failures:
            test_case_name, _, test_method_name = test_name.rpartition(".")
            test_app = test_name.split(".")[0]
            # Importing a test app that isn't installed raises RuntimeError.
            if test_app in settings.INSTALLED_APPS:
                test_case = import_string(test_case_name)
                test_method = getattr(test_case, test_method_name)
                setattr(test_case, test_method_name, expectedFailure(test_method))
        for reason, tests in self.connection.features.django_test_skips.items():
            for test_name in tests:
                test_case_name, _, test_method_name = test_name.rpartition(".")
                test_app = test_name.split(".")[0]
                # Importing a test app that isn't installed raises RuntimeError.
                if test_app in settings.INSTALLED_APPS:
                    test_case = import_string(test_case_name)
                    test_method = getattr(test_case, test_method_name)
                    setattr(test_case, test_method_name, skip(reason)(test_method))
