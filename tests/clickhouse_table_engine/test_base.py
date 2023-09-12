import os
import shutil
import tempfile
from contextlib import contextmanager
from importlib import import_module

from django.apps import apps
from django.db import connection, connections, migrations
from django.db import models as django_models
from django.db.migrations.migration import Migration
from django.db.migrations.recorder import MigrationRecorder
from django.db.migrations.state import ProjectState
from django.test import TransactionTestCase
from django.test.utils import extend_sys_path
from django.utils.module_loading import module_dir

from clickhouse_backend import models


class MigrationTestBase(TransactionTestCase):
    """
    Contains an extended set of asserts for testing migrations and schema operations.
    """

    available_apps = ["migrations"]
    databases = {"default", "s1r2", "s2r1", "other"}

    def tearDown(self):
        # Reset applied-migrations state.
        for db in self.databases:
            recorder = MigrationRecorder(connections[db])
            recorder.migration_qs.filter(app="migrations").delete()

    def get_table_description(self, table, using="default"):
        with connections[using].cursor() as cursor:
            return connections[using].introspection.get_table_description(cursor, table)

    def assertTableExists(self, table, using="default"):
        with connections[using].cursor() as cursor:
            self.assertIn(table, connections[using].introspection.table_names(cursor))

    def assertTableExistsCluster(self, table, dbs=("default", "s1r2", "s2r1")):
        for db in dbs:
            self.assertTableExists(table, db)

    def assertTableNotExists(self, table, using="default"):
        with connections[using].cursor() as cursor:
            self.assertNotIn(
                table, connections[using].introspection.table_names(cursor)
            )

    def assertTableNotExistsCluster(self, table, dbs=("default", "s1r2", "s2r1")):
        for db in dbs:
            self.assertTableNotExists(table, db)

    def assertColumnExists(self, table, column, using="default"):
        self.assertIn(
            column, [c.name for c in self.get_table_description(table, using=using)]
        )

    def assertColumnExistsCluster(self, table, column, dbs=("default", "s1r2", "s2r1")):
        for db in dbs:
            self.assertColumnExists(table, column, db)

    def assertColumnNotExists(self, table, column, using="default"):
        self.assertNotIn(
            column, [c.name for c in self.get_table_description(table, using=using)]
        )

    def assertColumnNotExistsCluster(
        self, table, column, dbs=("default", "s1r2", "s2r1")
    ):
        for db in dbs:
            self.assertColumnNotExists(table, column, db)

    def _get_column_allows_null(self, table, column, using):
        return [
            c.null_ok
            for c in self.get_table_description(table, using=using)
            if c.name == column
        ][0]

    def assertColumnNull(self, table, column, using="default"):
        self.assertTrue(self._get_column_allows_null(table, column, using))

    def assertColumnNullCluster(self, table, column, dbs=("default", "s1r2", "s2r1")):
        for db in dbs:
            self.assertColumnNull(table, column, db)

    def assertColumnNotNull(self, table, column, using="default"):
        self.assertFalse(self._get_column_allows_null(table, column, using))

    def assertColumnNotNullCluster(
        self, table, column, dbs=("default", "s1r2", "s2r1")
    ):
        for db in dbs:
            self.assertColumnNotNull(table, column, db)

    def assertIndexExists(
        self, table, columns, value=True, using="default", index_type=None
    ):
        with connections[using].cursor() as cursor:
            self.assertEqual(
                value,
                any(
                    c["index"]
                    for c in connections[using]
                    .introspection.get_constraints(cursor, table)
                    .values()
                    if (
                        c["columns"] == list(columns)
                        and (index_type is None or c["type"] == index_type)
                        and not c["unique"]
                    )
                ),
            )

    def assertIndexNotExists(self, table, columns):
        return self.assertIndexExists(table, columns, False)

    def assertIndexNameExists(self, table, index, using="default"):
        with connections[using].cursor() as cursor:
            self.assertIn(
                index,
                connection.introspection.get_constraints(cursor, table),
            )

    def assertIndexNameExistsCluster(
        self, table, index, dbs=("default", "s1r2", "s2r1")
    ):
        for db in dbs:
            self.assertIndexNameExists(table, index, db)

    def assertIndexNameNotExists(self, table, index, using="default"):
        with connections[using].cursor() as cursor:
            self.assertNotIn(
                index,
                connection.introspection.get_constraints(cursor, table),
            )

    def assertIndexNameNotExistsCluster(
        self, table, index, dbs=("default", "s1r2", "s2r1")
    ):
        for db in dbs:
            self.assertIndexNameNotExists(table, index, db)

    def assertConstraintExists(self, table, name, value=True, using="default"):
        with connections[using].cursor() as cursor:
            constraints = (
                connections[using].introspection.get_constraints(cursor, table).items()
            )
            self.assertEqual(
                value,
                any(c["check"] for n, c in constraints if n == name),
            )

    def assertConstraintNotExists(self, table, name):
        return self.assertConstraintExists(table, name, False)

    @contextmanager
    def temporary_migration_module(self, app_label="migrations", module=None):
        """
        Allows testing management commands in a temporary migrations module.

        Wrap all invocations to makemigrations and squashmigrations with this
        context manager in order to avoid creating migration files in your
        source tree inadvertently.

        Takes the application label that will be passed to makemigrations or
        squashmigrations and the Python path to a migrations module.

        The migrations module is used as a template for creating the temporary
        migrations module. If it isn't provided, the application's migrations
        module is used, if it exists.

        Returns the filesystem path to the temporary migrations module.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            target_dir = tempfile.mkdtemp(dir=temp_dir)
            with open(os.path.join(target_dir, "__init__.py"), "w"):
                pass
            target_migrations_dir = os.path.join(target_dir, "migrations")

            if module is None:
                module = apps.get_app_config(app_label).name + ".migrations"

            try:
                source_migrations_dir = module_dir(import_module(module))
            except (ImportError, ValueError):
                pass
            else:
                shutil.copytree(source_migrations_dir, target_migrations_dir)

            with extend_sys_path(temp_dir):
                new_module = os.path.basename(target_dir) + ".migrations"
                with self.settings(MIGRATION_MODULES={app_label: new_module}):
                    yield target_migrations_dir


class OperationTestBase(MigrationTestBase):
    """Common functions to help test operations."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._initial_table_names = frozenset(connection.introspection.table_names())

    def tearDown(self):
        self.cleanup_test_tables()
        super().tearDown()

    def cleanup_test_tables(self):
        table_names = (
            frozenset(connection.introspection.table_names())
            - self._initial_table_names
        )
        with connection.schema_editor() as editor, connection.cursor() as cursor:
            for table_name in table_names:
                cursor.execute(
                    "SELECT COUNT(*) > 1 FROM cluster('cluster', system.tables) where name=%s",
                    [table_name],
                )
                row = cursor.fetchone()
                is_on_cluster = row and row[0]
                if is_on_cluster:
                    on_cluster = "ON CLUSTER cluster SYNC"
                else:
                    on_cluster = ""
                editor.execute(
                    editor.sql_delete_table
                    % {
                        "table": editor.quote_name(table_name),
                        "on_cluster": on_cluster,
                    }
                )

    def apply_operations(self, app_label, project_state, operations, atomic=True):
        migration = Migration("name", app_label)
        migration.operations = operations
        with connection.schema_editor(atomic=atomic) as editor:
            return migration.apply(project_state, editor)

    def unapply_operations(self, app_label, project_state, operations, atomic=True):
        migration = Migration("name", app_label)
        migration.operations = operations
        with connection.schema_editor(atomic=atomic) as editor:
            return migration.unapply(project_state, editor)

    def make_test_state(self, app_label, operation, **kwargs):
        """
        Makes a test state using set_up_test_model and returns the
        original state and the state after the migration is applied.
        """
        project_state = self.set_up_distributed_model(app_label, **kwargs)
        new_state = project_state.clone()
        operation.state_forwards(app_label, new_state)
        return project_state, new_state

    def set_up_distributed_model(
        self,
        app_label,
        index=False,
        related_model=False,
        multicol_index=False,
        index_together=False,
        constraints=None,
        indexes=None,
    ):
        """Creates a test model state and database table."""
        meta_indexes = (
            [
                models.Index(
                    fields=("weight", "pink"),
                    name="weight_pink_idx",
                    type=models.Set(100),
                    granularity=10,
                )
            ]
            if index_together
            else []
        )

        operations = [
            migrations.CreateModel(
                "Pony",
                [
                    ("id", django_models.BigAutoField(primary_key=True)),
                    ("pink", models.Int32Field(default=3)),
                    ("weight", models.Float64Field()),
                ],
                options={
                    "indexes": meta_indexes,
                    "engine": models.ReplicatedMergeTree(order_by="id"),
                    "cluster": "cluster",
                },
            ),
            migrations.CreateModel(
                "PonyDistributed",
                [
                    ("id", django_models.BigAutoField(primary_key=True)),
                    ("pink", models.Int32Field(default=3)),
                    ("weight", models.Float64Field()),
                ],
                options={
                    "engine": models.Distributed(
                        "cluster", models.currentDatabase(), f"{app_label}_pony"
                    ),
                    "cluster": "cluster",
                },
            ),
        ]

        if index:
            operations.append(
                migrations.AddIndex(
                    "pony",
                    models.Index(
                        fields=["pink"],
                        name="pony_pink_idx",
                        type=models.Set(100),
                        granularity=10,
                    ),
                )
            )
        if multicol_index:
            operations.append(
                migrations.AddIndex(
                    "pony",
                    models.Index(
                        fields=["pink", "weight"],
                        name="pony_test_idx",
                        type=models.Set(100),
                        granularity=10,
                    ),
                )
            )
        if indexes:
            for index in indexes:
                operations.append(migrations.AddIndex("pony", index))
        if constraints:
            for constraint in constraints:
                operations.append(migrations.AddConstraint("pony", constraint))
        if related_model:
            operations.append(
                migrations.CreateModel(
                    "Rider",
                    [
                        ("id", django_models.BigAutoField(primary_key=True)),
                        (
                            "pony",
                            django_models.ForeignKey("Pony", django_models.CASCADE),
                        ),
                        (
                            "friend",
                            django_models.ForeignKey(
                                "self", django_models.CASCADE, null=True
                            ),
                        ),
                    ],
                    options={
                        "engine": models.ReplicatedMergeTree(order_by="id"),
                        "cluster": "cluster",
                    },
                )
            )
            operations.append(
                migrations.CreateModel(
                    "RiderDistributed",
                    [
                        ("id", django_models.BigAutoField(primary_key=True)),
                        (
                            "pony",
                            django_models.ForeignKey(
                                "PonyDistributed", django_models.CASCADE
                            ),
                        ),
                        (
                            "friend",
                            django_models.ForeignKey(
                                "self", django_models.CASCADE, null=True
                            ),
                        ),
                    ],
                    options={
                        "engine": models.Distributed(
                            "cluster", models.currentDatabase(), f"{app_label}_rider"
                        ),
                        "cluster": "cluster",
                    },
                )
            )

        return self.apply_operations(app_label, ProjectState(), operations)
