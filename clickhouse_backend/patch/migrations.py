from django.apps.registry import Apps
from django.conf import settings
from django.db import DatabaseError
from django.db import models as django_models
from django.db.migrations.exceptions import MigrationSchemaMissing
from django.db.migrations.recorder import MigrationRecorder
from django.utils.functional import cached_property
from django.utils.timezone import now

from clickhouse_backend import models

__all__ = ["patch_migrations", "patch_migration_recorder"]


def patch_migrations():
    patch_migration_recorder()


def patch_migration_recorder():
    def Migration(self):
        """
        Lazy load to avoid AppRegistryNotReady if installed apps import
        MigrationRecorder.
        """
        if self._migration_class is None:
            if self.connection.vendor == "clickhouse":
                if getattr(settings, "CLICKHOUSE_MIGRATION_ON_CLUSTER", None):

                    class Migration(models.ClickhouseModel):
                        app = models.StringField(max_length=255)
                        name = models.StringField(max_length=255)
                        applied = models.DateTime64Field(default=now)

                        class Meta:
                            apps = Apps()
                            app_label = "migrations"
                            db_table = "django_migrations"
                            engine = models.Distributed(
                                settings.CLICKHOUSE_MIGRATION_ON_CLUSTER,
                                models.currentDatabase(),
                                "django_migrations_local",
                            )
                            cluster = settings.CLICKHOUSE_MIGRATION_ON_CLUSTER

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
                            engine = models.MergeTree(order_by=("id",))

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

    def ensure_schema(self):
        if self.has_table():
            return
        try:
            with self.connection.schema_editor() as editor:
                if self.connection.vendor == "clickhouse" and getattr(
                    settings, "CLICKHOUSE_MIGRATION_ON_CLUSTER", None
                ):
                    from clickhouse_backend import models

                    class LocalMigration(models.ClickhouseModel):
                        app = models.StringField(max_length=255)
                        name = models.StringField(max_length=255)
                        applied = models.DateTime64Field(default=now)

                        class Meta:
                            apps = Apps()
                            app_label = "migrations"
                            db_table = "django_migrations_local"
                            engine = models.ReplicatedMergeTree(
                                "/clickhouse/tables/{shard}/{database}/{table}",
                                "{replica}",
                            )
                            cluster = settings.CLICKHOUSE_MIGRATION_ON_CLUSTER

                        def __str__(self):
                            return "Migration %s for %s" % (self.name, self.app)

                    editor.create_model(LocalMigration)
                editor.create_model(self.Migration)
        except DatabaseError as exc:
            raise MigrationSchemaMissing(
                "Unable to create the django_migrations table (%s)" % exc
            )

    def record_applied(self, app, name):
        """Record that a migration was applied."""
        self.ensure_schema()
        if self.connection.vendor == "clickhouse" and getattr(
            settings, "CLICKHOUSE_MIGRATION_ON_CLUSTER", None
        ):
            self.migration_qs.settings(insert_distributed_sync=1).create(
                app=app, name=name
            )
        else:
            self.migration_qs.create(app=app, name=name)

    def record_unapplied(self, app, name):
        """Record that a migration was unapplied."""
        self.ensure_schema()
        if self.connection.vendor == "clickhouse":
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

    cachedMigration = cached_property(Migration)
    cachedMigration.__set_name__(MigrationRecorder, "Migration")
    MigrationRecorder.Migration = cachedMigration
    MigrationRecorder.ensure_schema = ensure_schema
    MigrationRecorder.record_applied = record_applied
    MigrationRecorder.record_unapplied = record_unapplied
    MigrationRecorder.flush = flush
