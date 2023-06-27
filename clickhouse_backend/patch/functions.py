from django.db.models import functions


def random_as_clickhouse(self, compiler, connection, **extra_context):
    return functions.Random.as_sql(
        self, compiler, connection, function="rand64", **extra_context
    )


def patch_functions():
    functions.Random.as_clickhouse = random_as_clickhouse
