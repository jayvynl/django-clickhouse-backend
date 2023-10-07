from django.apps.registry import Apps
from django.db import models as django_models
from django.db.migrations import Migration
from django.db.migrations.exceptions import IrreversibleError
from django.db.migrations.operations.fields import FieldOperation
from django.db.migrations.operations.models import (
    DeleteModel,
    IndexOperation,
    ModelOperation,
    RenameModel,
)
from django.db.migrations.recorder import MigrationRecorder
from django.utils.timezone import now

__all__ = ["patch_migrations", "patch_migration_recorder", "patch_migration"]


def patch_migrations():
    patch_migration_recorder()
    patch_migration()


def patch_migration_recorder():
    def Migration(self):
        """
        Lazy load to avoid AppRegistryNotReady if installed apps import
        MigrationRecorder.
        """
        if self._migration_class is None:
            if self.connection.vendor == "clickhouse":
                from clickhouse_backend import models

                class Migration(models.ClickhouseModel):
                    app = models.StringField(max_length=255)
                    name = models.StringField(max_length=255)
                    applied = models.DateTime64Field(default=now)
                    deleted = models.BoolField(default=False)

                    class Meta:
                        apps = Apps()
                        app_label = "migrations"
                        db_table = "django_migrations"
                        engine = models.MergeTree(order_by=("app", "name"))
                        cluster = getattr(self.connection, "migration_cluster", None)

                    def __str__(self):
                        return "Migration %s for %s" % (self.name, self.app)

            else:

                class Migration(django_models.Model):
                    app = django_models.CharField(max_length=255)
                    name = django_models.CharField(max_length=255)
                    applied = django_models.DateTimeField(default=now)

                    class Meta:
                        apps = Apps()
                        app_label = "migrations"
                        db_table = "django_migrations"

                    def __str__(self):
                        return "Migration %s for %s" % (self.name, self.app)

            self._migration_class = Migration
        return self._migration_class

    def has_table(self):
        """Return True if the django_migrations table exists."""
        # Assert migration table won't be deleted once created.
        if not getattr(self, "_has_table", False):
            with self.connection.cursor() as cursor:
                tables = self.connection.introspection.table_names(cursor)
                self._has_table = self.Migration._meta.db_table in tables
                if self._has_table and self.connection.vendor == "clickhouse":
                    # fix https://github.com/jayvynl/django-clickhouse-backend/issues/51
                    cursor.execute(
                        "ALTER table django_migrations ADD COLUMN IF NOT EXISTS deleted Bool"
                    )
        return self._has_table

    def migration_qs(self):
        if self.connection.vendor == "clickhouse":
            return self.Migration.objects.using(self.connection.alias).filter(
                deleted=False
            )
        return self.Migration.objects.using(self.connection.alias)

    def record_applied(self, app, name):
        """Record that a migration was applied."""
        self.ensure_schema()
        if self.connection.vendor == "clickhouse" and (
            self.Migration.objects.using(self.connection.alias)
            .filter(app=app, name=name)
            .exists()
        ):
            self.Migration.objects.using(self.connection.alias).filter(
                app=app, name=name
            ).settings(mutations_sync=1).update(deleted=False)
        else:
            self.migration_qs.create(app=app, name=name)

    def record_unapplied(self, app, name):
        """Record that a migration was unapplied."""
        self.ensure_schema()
        if self.connection.vendor == "clickhouse":
            self.migration_qs.filter(app=app, name=name).settings(
                mutations_sync=1
            ).update(deleted=True)
        else:
            self.migration_qs.filter(app=app, name=name).delete()

    def flush(self):
        """Delete all migration records. Useful for testing migrations."""
        if self.connection.vendor == "clickhouse":
            self.migration_qs.settings(mutations_sync=1).delete()
        else:
            self.migration_qs.all().delete()

    MigrationRecorder.Migration = property(Migration)
    MigrationRecorder.has_table = has_table
    MigrationRecorder.migration_qs = property(migration_qs)
    MigrationRecorder.record_applied = record_applied
    MigrationRecorder.record_unapplied = record_unapplied
    MigrationRecorder.flush = flush


def patch_migration():
    def apply(self, project_state, schema_editor, collect_sql=False):
        """
        Take a project_state representing all migrations prior to this one
        and a schema_editor for a live database and apply the migration
        in a forwards order.

        Return the resulting project state for efficient reuse by following
        Migrations.
        """
        applied_on_remote = False
        if getattr(schema_editor.connection, "migration_cluster", None):
            with schema_editor.connection.cursor() as cursor:
                cursor.execute(
                    "select EXISTS(select 1 from clusterAllReplicas(%s, currentDatabase(), %s)"
                    " where app=%s and name=%s and deleted=false)",
                    [
                        schema_editor.connection.migration_cluster,
                        "django_migrations",
                        self.app_label,
                        self.name,
                    ],
                )
                (applied_on_remote,) = cursor.fetchone()
        for operation in self.operations:
            # If this operation cannot be represented as SQL, place a comment
            # there instead
            if collect_sql:
                schema_editor.collected_sql.append("--")
                schema_editor.collected_sql.append("-- %s" % operation.describe())
                schema_editor.collected_sql.append("--")
                if not operation.reduces_to_sql:
                    schema_editor.collected_sql.append(
                        "-- THIS OPERATION CANNOT BE WRITTEN AS SQL"
                    )
                    continue
                collected_sql_before = len(schema_editor.collected_sql)
            # Save the state before the operation has run
            old_state = project_state.clone()
            operation.state_forwards(self.app_label, project_state)

            # Run the operation
            # Ensure queries on cluster are only executed once.
            model_name = None
            skip_database_forwards = False
            if isinstance(operation, (IndexOperation, FieldOperation)):
                model_name = operation.model_name_lower
            elif isinstance(operation, ModelOperation):
                model_name = operation.name_lower
            if model_name:
                if isinstance(operation, (RenameModel, DeleteModel)):
                    model_state = old_state.models[self.app_label, model_name]
                else:
                    model_state = project_state.models[self.app_label, model_name]
                if model_state.options.get("cluster") and applied_on_remote:
                    skip_database_forwards = True
            if not skip_database_forwards:
                operation.database_forwards(
                    self.app_label, schema_editor, old_state, project_state
                )
            if collect_sql and collected_sql_before == len(schema_editor.collected_sql):
                schema_editor.collected_sql.append("-- (no-op)")
        return project_state

    def unapply(self, project_state, schema_editor, collect_sql=False):
        """
        Take a project_state representing all migrations prior to this one
        and a schema_editor for a live database and apply the migration
        in a reverse order.

        The backwards migration process consists of two phases:

        1. The intermediate states from right before the first until right
           after the last operation inside this migration are preserved.
        2. The operations are applied in reverse order using the states
           recorded in step 1.
        """
        unapplied_on_remote = False
        if getattr(schema_editor.connection, "migration_cluster", None):
            with schema_editor.connection.cursor() as cursor:
                cursor.execute(
                    "select EXISTS(select 1 from clusterAllReplicas(%s, currentDatabase(), %s)"
                    " where app=%s and name=%s and deleted=true)",
                    [
                        schema_editor.connection.migration_cluster,
                        "django_migrations",
                        self.app_label,
                        self.name,
                    ],
                )
                (unapplied_on_remote,) = cursor.fetchone()
        # Construct all the intermediate states we need for a reverse migration
        to_run = []
        new_state = project_state
        # Phase 1
        for operation in self.operations:
            # If it's irreversible, error out
            if not operation.reversible:
                raise IrreversibleError(
                    "Operation %s in %s is not reversible" % (operation, self)
                )
            # Preserve new state from previous run to not tamper the same state
            # over all operations
            new_state = new_state.clone()
            old_state = new_state.clone()
            operation.state_forwards(self.app_label, new_state)
            to_run.insert(0, (operation, old_state, new_state))

        # Phase 2
        for operation, to_state, from_state in to_run:
            if collect_sql:
                schema_editor.collected_sql.append("--")
                schema_editor.collected_sql.append("-- %s" % operation.describe())
                schema_editor.collected_sql.append("--")
                if not operation.reduces_to_sql:
                    schema_editor.collected_sql.append(
                        "-- THIS OPERATION CANNOT BE WRITTEN AS SQL"
                    )
                    continue
                collected_sql_before = len(schema_editor.collected_sql)
            # Ensure queries on cluster are only executed once.
            model_name = None
            skip_database_backwards = False
            if isinstance(operation, (IndexOperation, FieldOperation)):
                model_name = operation.model_name_lower
            elif isinstance(operation, ModelOperation):
                model_name = operation.name_lower
            if model_name:
                if isinstance(operation, (RenameModel, DeleteModel)):
                    model_state = to_state.models[self.app_label, model_name]
                else:
                    model_state = from_state.models[self.app_label, model_name]
                if model_state.options.get("cluster") and unapplied_on_remote:
                    skip_database_backwards = True
            if not skip_database_backwards:
                operation.database_backwards(
                    self.app_label, schema_editor, from_state, to_state
                )
            if collect_sql and collected_sql_before == len(schema_editor.collected_sql):
                schema_editor.collected_sql.append("-- (no-op)")
        return project_state

    Migration.apply = apply
    Migration.unapply = unapply
