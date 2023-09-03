from django.apps.registry import Apps
from django.db import DatabaseError
from django.db import models as django_models
from django.db.migrations import Migration
from django.db.migrations.exceptions import MigrationSchemaMissing
from django.db.migrations.operations.fields import FieldOperation
from django.db.migrations.operations.models import (
    DeleteModel,
    IndexOperation,
    ModelOperation,
    RenameModel,
)
from django.db.migrations.recorder import MigrationRecorder
from django.utils.timezone import now

from clickhouse_backend import models

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
                if self.connection.settings_dict.get("migration_on_cluster"):

                    class Migration(models.ClickhouseModel):
                        host = models.StringField(max_length=255)
                        app = models.StringField(max_length=255)
                        name = models.StringField(max_length=255)
                        applied = models.DateTime64Field(default=now)
                        deleted = models.BoolField(default=False)

                        class Meta:
                            apps = Apps()
                            app_label = "migrations"
                            db_table = "django_migrations"
                            engine = models.ReplicatedMergeTree(
                                "/clickhouse/tables/{shard}/{database}/{table}",
                                "{replica}",
                                order_by=("app", "name"),
                            )
                            cluster = self.connection.settings_dict[
                                "migration_on_cluster"
                            ]

                        def __str__(self):
                            return "Migration %s for %s" % (self.name, self.app)

                else:

                    class Migration(models.ClickhouseModel):
                        app = models.StringField(max_length=255)
                        name = models.StringField(max_length=255)
                        applied = models.DateTime64Field(default=now)

                        class Meta:
                            apps = Apps()
                            app_label = "migrations"
                            db_table = "django_migrations"
                            engine = models.MergeTree(order_by=("app", "name"))

                        def __str__(self):
                            return "Migration %s for %s" % (self.name, self.app)

            else:

                class Migration(django_models.Model):
                    app = django_models.CharField(max_length=255)
                    name = django_models.CharField(max_length=255)
                    applied = models.DateTimeField(default=now)

                    class Meta:
                        apps = Apps()
                        app_label = "migrations"
                        db_table = "django_migrations"

                    def __str__(self):
                        return "Migration %s for %s" % (self.name, self.app)

            self._migration_class = Migration
        return self._migration_class

    def MigrationDistributed(self):
        if not hasattr(self, "_migration_distributed_class"):
            if (
                self.connection.vendor == "clickhouse"
                and self.connection.settings_dict.get("migration_on_cluster")
            ):

                class MigrationDistributed(models.ClickhouseModel):
                    host = models.StringField(max_length=255)
                    app = models.StringField(max_length=255)
                    name = models.StringField(max_length=255)
                    applied = models.DateTime64Field(default=now)
                    deleted = models.BoolField(default=False)

                    class Meta:
                        apps = Apps()
                        app_label = "migrations"
                        db_table = "django_migrations_distributed"
                        engine = models.Distributed(
                            self.connection.settings_dict["migration_on_cluster"],
                            models.currentDatabase(),
                            "django_migrations",
                        )
                        cluster = self.connection.settings_dict["migration_on_cluster"]

                    def __str__(self):
                        return "Migration %s for %s" % (self.name, self.app)

                self._migration_distributed_class = MigrationDistributed
            else:
                self._migration_distributed_class = None
        return self._migration_distributed_class

    def migration_qs(self):
        if self.MigrationDistributed is not None:
            return self.Migration.objects.using(self.connection.alias).filter(
                host=models.hostName(), deleted=False
            )
        return self.Migration.objects.using(self.connection.alias)

    def ensure_schema(self):
        if self.has_table():
            return
        try:
            with self.connection.schema_editor() as editor:
                editor.create_model(self.Migration)
                if self.MigrationDistributed is not None:
                    editor.create_model(self.MigrationDistributed)
        except DatabaseError as exc:
            raise MigrationSchemaMissing(
                "Unable to create the django_migrations table (%s)" % exc
            )

    def record_applied(self, app, name):
        """Record that a migration was applied."""
        self.ensure_schema()
        if self.MigrationDistributed is not None:
            if (
                self.Migration.objects.using(self.connection.alias)
                .filter(host=models.hostName(), app=app, name=name)
                .exists()
            ):
                self.Migration.objects.using(self.connection.alias).settings(
                    mutations_sync=1
                ).filter(host=models.hostName(), app=app, name=name).update(
                    deleted=False
                )
            else:
                self.migration_qs.create(host=models.hostName(), app=app, name=name)
        else:
            self.migration_qs.create(app=app, name=name)

    def record_unapplied(self, app, name):
        """Record that a migration was unapplied."""
        self.ensure_schema()
        if self.connection.vendor == "clickhouse":
            if self.MigrationDistributed is not None:
                self.migration_qs.settings(mutations_sync=1).filter(
                    app=app, name=name
                ).update(deleted=True)
            else:
                self.migration_qs.settings(mutations_sync=1).filter(
                    app=app, name=name
                ).delete()
        else:
            self.migration_qs.filter(app=app, name=name).delete()

    def flush(self):
        """Delete all migration records. Useful for testing migrations."""
        if self.connection.vendor == "clickhouse":
            self.migration_qs.settings(mutations_sync=1).delete()
        else:
            self.migration_qs.all().delete()

    MigrationRecorder.Migration = property(Migration)
    MigrationRecorder.MigrationDistributed = property(MigrationDistributed)
    MigrationRecorder.migration_qs = property(migration_qs)
    MigrationRecorder.ensure_schema = ensure_schema
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
            # ensure queries on cluster are only executed once.
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
                if model_state.options.get(
                    "cluster"
                ) and schema_editor.connection.settings_dict.get(
                    "migration_on_cluster"
                ):
                    recorder = MigrationRecorder(schema_editor.connection)
            operation.database_forwards(
                self.app_label, schema_editor, old_state, project_state
            )
            if collect_sql and collected_sql_before == len(schema_editor.collected_sql):
                schema_editor.collected_sql.append("-- (no-op)")
        return project_state

    Migration.apply
