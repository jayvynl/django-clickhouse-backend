from django.db.migrations import Migration
from django.db.migrations.exceptions import IrreversibleError
from django.db.migrations.operations.fields import FieldOperation
from django.db.migrations.operations.models import (
    DeleteModel,
    IndexOperation,
    ModelOperation,
    RenameModel,
)

from .recorder import _get_model_table_name


def _check_applied_on_remote(connection, app_label, name, *, deleted):
    migration_cluster = getattr(connection, "migration_cluster", None)
    if not migration_cluster:
        return False

    table = _get_model_table_name(connection)
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT EXISTS("
            "  SELECT 1 FROM clusterAllReplicas(%s, currentDatabase(), %s)"
            "  WHERE app = %s AND name = %s AND deleted = %s"
            ")",
            [migration_cluster, table, app_label, name, deleted],
        )
        (exists,) = cursor.fetchone()
    return exists


def _get_operation_model_name(operation):
    if isinstance(operation, (IndexOperation, FieldOperation)):
        return operation.model_name_lower
    elif isinstance(operation, ModelOperation):
        return operation.name_lower
    return None


def _should_skip_operation(operation, model_name, app_label, old_state, new_state):
    if not model_name:
        return False
    if isinstance(operation, (RenameModel, DeleteModel)):
        model_state = old_state.models[app_label, model_name]
    else:
        model_state = new_state.models[app_label, model_name]
    return bool(model_state.options.get("cluster"))


def _patched_apply(self, project_state, schema_editor, collect_sql=False):
    applied_on_remote = _check_applied_on_remote(
        schema_editor.connection, self.app_label, self.name, deleted=False
    )
    for operation in self.operations:
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

        old_state = project_state.clone()
        operation.state_forwards(self.app_label, project_state)

        model_name = _get_operation_model_name(operation)
        skip = applied_on_remote and _should_skip_operation(
            operation, model_name, self.app_label, old_state, project_state
        )
        if not skip:
            operation.database_forwards(
                self.app_label, schema_editor, old_state, project_state
            )
        if collect_sql and collected_sql_before == len(schema_editor.collected_sql):
            schema_editor.collected_sql.append("-- (no-op)")
    return project_state


def _patched_unapply(self, project_state, schema_editor, collect_sql=False):
    unapplied_on_remote = _check_applied_on_remote(
        schema_editor.connection, self.app_label, self.name, deleted=True
    )
    to_run = []
    new_state = project_state
    for operation in self.operations:
        if not operation.reversible:
            raise IrreversibleError(
                "Operation %s in %s is not reversible" % (operation, self)
            )
        new_state = new_state.clone()
        old_state = new_state.clone()
        operation.state_forwards(self.app_label, new_state)
        to_run.insert(0, (operation, old_state, new_state))

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

        model_name = _get_operation_model_name(operation)
        skip = unapplied_on_remote and _should_skip_operation(
            operation, model_name, self.app_label, to_state, from_state
        )
        if not skip:
            operation.database_backwards(
                self.app_label, schema_editor, from_state, to_state
            )
        if collect_sql and collected_sql_before == len(schema_editor.collected_sql):
            schema_editor.collected_sql.append("-- (no-op)")
    return project_state


def install_cluster_patches():
    Migration.apply = _patched_apply
    Migration.unapply = _patched_unapply
