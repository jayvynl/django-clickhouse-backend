from django.apps.registry import Apps
from django.db import DatabaseError
from django.db import models as django_models
from django.db.migrations.exceptions import MigrationSchemaMissing
from django.db.migrations.recorder import MigrationRecorder
from django.utils.timezone import now


def _should_distribute_migrations(connection):
    return getattr(connection, "distributed_migrations", False) and getattr(
        connection, "migration_cluster", None
    )


def _get_model_table_name(connection):
    if _should_distribute_migrations(connection):
        return "distributed_django_migrations"
    return "django_migrations"


def _get_replicas(cluster_name, cursor):
    cursor.execute(
        "SELECT replica_num FROM system.clusters WHERE cluster = %s",
        [cluster_name],
    )
    res = cursor.fetchone()
    if not res:
        return 0
    return res[0]


def _check_replicas(connection):
    if hasattr(connection, "has_replicas"):
        return connection.has_replicas
    with connection.cursor() as cursor:
        return _get_replicas(connection.migration_cluster, cursor) >= 1


def _build_clickhouse_migration_model(connection):
    # Lazy import: clickhouse_backend.models triggers ClickhouseModel(models.Model)
    # which requires the app registry to be ready.
    from clickhouse_backend import models
    from clickhouse_backend.models import currentDatabase

    if _should_distribute_migrations(connection):
        has_replicas = _check_replicas(connection)
        connection.has_replicas = has_replicas

        Engine = models.ReplicatedMergeTree if has_replicas else models.MergeTree

        class _LocalMigration(models.ClickhouseModel):
            app = models.StringField(max_length=255)
            name = models.StringField(max_length=255)
            applied = models.DateTime64Field(default=now)
            deleted = models.BoolField(default=False)

            class Meta:
                apps = Apps()
                app_label = "migrations"
                db_table = "django_migrations"
                engine = Engine(order_by=("app", "name"))
                cluster = connection.migration_cluster

            def __str__(self):
                return "Migration %s for %s" % (self.name, self.app)

        class Migration(models.ClickhouseModel):
            app = models.StringField(max_length=255)
            name = models.StringField(max_length=255)
            applied = models.DateTime64Field(default=now)
            deleted = models.BoolField(default=False)

            class Meta:
                apps = Apps()
                app_label = "migrations"
                db_table = _get_model_table_name(connection)
                engine = models.Distributed(
                    connection.migration_cluster,
                    currentDatabase(),
                    _LocalMigration._meta.db_table,
                    models.Rand(),
                )
                cluster = connection.migration_cluster

        Migration._meta.local_model_class = _LocalMigration
        return Migration

    else:

        class Migration(models.ClickhouseModel):
            app = models.StringField(max_length=255)
            name = models.StringField(max_length=255)
            applied = models.DateTime64Field(default=now)
            deleted = models.BoolField(default=False)

            class Meta:
                apps = Apps()
                app_label = "migrations"
                db_table = _get_model_table_name(connection)
                engine = models.MergeTree(order_by=("app", "name"))
                cluster = getattr(connection, "migration_cluster", None)

            def __str__(self):
                return "Migration %s for %s" % (self.name, self.app)

        return Migration


def _build_django_migration_model():
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

    return Migration


def migration_property(self):
    if self._migration_class is None:
        if self.connection.vendor == "clickhouse":
            self._migration_class = _build_clickhouse_migration_model(self.connection)
        else:
            self._migration_class = _build_django_migration_model()
    return self._migration_class


def has_table(self):
    """Return True if the django_migrations table exists."""
    if not getattr(self, "_has_table", False):
        with self.connection.cursor() as cursor:
            table = self.Migration._meta.db_table
            tables = self.connection.introspection.table_names(cursor)
            self._has_table = table in tables
            if self._has_table and self.connection.vendor == "clickhouse":
                cursor.execute(
                    "SELECT EXISTS("
                    "  SELECT 1 FROM system.columns"
                    "  WHERE database = currentDatabase()"
                    "    AND table = %s"
                    "    AND name = 'deleted'"
                    ")",
                    [table],
                )
                (deleted_exists,) = cursor.fetchone()
                if not deleted_exists:
                    cursor.execute(
                        "ALTER TABLE %s ADD COLUMN IF NOT EXISTS deleted Bool"
                        % self.connection.ops.quote_name(table)
                    )
    return self._has_table


def ensure_schema(self):
    """Ensure the table exists and has the correct schema."""
    if self.has_table():
        return
    try:
        with self.connection.schema_editor() as editor:
            if (
                editor.connection.vendor == "clickhouse"
                and _should_distribute_migrations(editor.connection)
            ):
                with editor.connection.cursor() as cursor:
                    tables = editor.connection.introspection.table_names(cursor)
                local_model_class = self.Migration._meta.local_model_class
                if local_model_class._meta.db_table not in tables:
                    editor.create_model(local_model_class)
            editor.create_model(self.Migration)
    except DatabaseError as exc:
        raise MigrationSchemaMissing(
            "Unable to create the django_migrations table (%s)" % exc
        )


def migration_qs_property(self):
    if self.connection.vendor == "clickhouse":
        return self.Migration.objects.using(self.connection.alias).filter(deleted=False)
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
        self.migration_qs.filter(app=app, name=name).settings(mutations_sync=1).update(
            deleted=True
        )
    else:
        self.migration_qs.filter(app=app, name=name).delete()


def flush(self):
    """Delete all migration records."""
    if self.connection.vendor == "clickhouse":
        self.migration_qs.settings(mutations_sync=1).delete()
    else:
        self.migration_qs.all().delete()


def install_recorder_patches():
    MigrationRecorder.Migration = property(migration_property)
    MigrationRecorder.has_table = has_table
    MigrationRecorder.ensure_schema = ensure_schema
    MigrationRecorder.migration_qs = property(migration_qs_property)
    MigrationRecorder.record_applied = record_applied
    MigrationRecorder.record_unapplied = record_unapplied
    MigrationRecorder.flush = flush
