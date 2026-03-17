from django.db.models import functions

__all__ = ["patch_functions", "patch_random"]


def patch_functions():
    patch_now()
    patch_random()


def patch_now():
    if hasattr(functions.Now, "as_clickhouse"):
        return

    def as_clickhouse(self, compiler, connection, **extra_context):
        return functions.Now.as_sql(
            self, compiler, connection, template="now64()", **extra_context
        )

    functions.Now.as_clickhouse = as_clickhouse


def patch_random():
    if hasattr(functions.Random, "as_clickhouse"):
        return

    def as_clickhouse(self, compiler, connection, **extra_context):
        return functions.Random.as_sql(
            self, compiler, connection, function="rand64", **extra_context
        )

    functions.Random.as_clickhouse = as_clickhouse
