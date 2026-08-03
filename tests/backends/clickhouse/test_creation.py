from contextlib import contextmanager
from io import StringIO
from unittest import mock

from clickhouse_driver.errors import ErrorCodes, ServerException
from django.db import DatabaseError, connection
from django.db.backends.base.creation import BaseDatabaseCreation
from django.test import SimpleTestCase

from clickhouse_backend.backend.creation import DatabaseCreation


class DatabaseCreationTests(SimpleTestCase):
    @contextmanager
    def changed_test_settings(self, **kwargs):
        settings = connection.settings_dict["TEST"]
        saved_values = {}
        for name in kwargs:
            if name in settings:
                saved_values[name] = settings[name]

        for name, value in kwargs.items():
            settings[name] = value
        try:
            yield
        finally:
            for name in kwargs:
                if name in saved_values:
                    settings[name] = saved_values[name]
                else:
                    del settings[name]

    def _execute_raise_database_already_exists(self, cursor, parameters, keepdb=False):
        server_error = ServerException(
            "Database test already exists.", ErrorCodes.DATABASE_ALREADY_EXISTS
        )
        error = DatabaseError(server_error)
        raise DatabaseError(server_error) from error

    def _execute_raise_unhandled(self, cursor, parameters, keepdb=False):
        server_error = ServerException("", ErrorCodes.DATABASE_ACCESS_DENIED)
        error = DatabaseError(server_error)
        raise DatabaseError() from error

    def patch_test_db_creation(self, execute_create_test_db):
        return mock.patch.object(
            BaseDatabaseCreation, "_execute_create_test_db", execute_create_test_db
        )

    @mock.patch("sys.stdout", new_callable=StringIO)
    @mock.patch("sys.stderr", new_callable=StringIO)
    def test_create_test_db(self, *mocked_objects):
        creation = DatabaseCreation(connection)
        # Simulate test database creation raising "database already exists"
        with self.patch_test_db_creation(self._execute_raise_database_already_exists):
            with mock.patch("builtins.input", return_value="no"):
                with self.assertRaises(SystemExit):
                    # SystemExit is raised if the user answers "no" to the
                    # prompt asking if it's okay to delete the test database.
                    creation._create_test_db(
                        verbosity=0, autoclobber=False, keepdb=False
                    )
            # "Database already exists" error is ignored when keepdb is on
            creation._create_test_db(verbosity=0, autoclobber=False, keepdb=True)
        # Simulate test database creation raising unexpected error
        with self.patch_test_db_creation(self._execute_raise_unhandled):
            with mock.patch.object(
                DatabaseCreation, "_database_exists", return_value=False
            ):
                with self.assertRaises(SystemExit):
                    creation._create_test_db(
                        verbosity=0, autoclobber=False, keepdb=False
                    )
                with self.assertRaises(SystemExit):
                    creation._create_test_db(
                        verbosity=0, autoclobber=False, keepdb=True
                    )
        # Simulate test database creation raising "insufficient privileges".
        # An error shouldn't appear when keepdb is on and the database already
        # exists.
        with self.patch_test_db_creation(self._execute_raise_unhandled):
            with mock.patch.object(
                DatabaseCreation, "_database_exists", return_value=True
            ):
                creation._create_test_db(verbosity=0, autoclobber=False, keepdb=True)

    def test_clone_test_db_creates_and_migrates_clone(self):
        creation = DatabaseCreation(connection)
        source_name = connection.settings_dict["NAME"]
        target_name = creation.get_test_db_clone_settings("3")["NAME"]

        # Capture the database the migration is run against so we can assert the
        # connection is pointed at the clone while migrating and restored after.
        migrated_against = []

        def fake_migrate(*args, **kwargs):
            migrated_against.append(connection.settings_dict["NAME"])

        with mock.patch.object(
            BaseDatabaseCreation, "_execute_create_test_db"
        ) as execute_create, mock.patch(
            "clickhouse_backend.backend.creation.call_command", side_effect=fake_migrate
        ) as call_command:
            creation._clone_test_db(suffix="3", verbosity=0, keepdb=False)

        # The clone database was created with the "<name>_<suffix>" name.
        execute_create.assert_called_once()
        # call_args.args/kwargs require Python 3.8+; use tuple indexing for 3.7.
        create_args, _create_kwargs = execute_create.call_args
        params = create_args[1]
        self.assertEqual(params["dbname"], connection.ops.quote_name(target_name))
        # Schema is reproduced by re-running migrations against the clone.
        call_command.assert_called_once()
        migrate_args, migrate_kwargs = call_command.call_args
        self.assertEqual(migrate_args[0], "migrate")
        self.assertTrue(migrate_kwargs["run_syncdb"])
        self.assertEqual(migrated_against, [target_name])
        # The connection is restored to the source database afterwards.
        self.assertEqual(connection.settings_dict["NAME"], source_name)

    def test_clone_test_db_keepdb_existing_skips_work(self):
        creation = DatabaseCreation(connection)
        with mock.patch.object(
            DatabaseCreation, "_database_exists", return_value=True
        ), mock.patch.object(
            BaseDatabaseCreation, "_execute_create_test_db"
        ) as execute_create, mock.patch(
            "clickhouse_backend.backend.creation.call_command"
        ) as call_command:
            creation._clone_test_db(suffix="3", verbosity=0, keepdb=True)

        # An existing clone that is being kept is left untouched.
        execute_create.assert_not_called()
        call_command.assert_not_called()

    def test_clone_test_db_unmanaged_migrates_without_creating(self):
        """An unmanaged alias skips CREATE DATABASE but still migrates."""
        creation = DatabaseCreation(connection)
        source_name = connection.settings_dict["NAME"]
        target_name = creation.get_test_db_clone_settings("3")["NAME"]

        migrated_against = []

        def fake_migrate(*args, **kwargs):
            migrated_against.append(connection.settings_dict["NAME"])

        with self.changed_test_settings(managed=False):
            with mock.patch.object(
                BaseDatabaseCreation, "_execute_create_test_db"
            ) as execute_create, mock.patch(
                "clickhouse_backend.backend.creation.call_command",
                side_effect=fake_migrate,
            ) as call_command:
                creation._clone_test_db(suffix="3", verbosity=0, keepdb=False)
        execute_create.assert_not_called()
        call_command.assert_called_once()
        migrate_args, migrate_kwargs = call_command.call_args
        self.assertEqual(migrate_args[0], "migrate")
        self.assertTrue(migrate_kwargs["run_syncdb"])
        self.assertEqual(migrate_kwargs["database"], connection.alias)
        # The clone is migrated, not the source database.
        self.assertEqual(migrated_against, [target_name])
        self.assertEqual(connection.settings_dict["NAME"], source_name)
