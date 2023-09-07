from django.db.models import functions

__all__ = [
    "patch_functions",
    "patch_random",
]


def patch_functions():
    patch_random()


def patch_random():
    def random_as_clickhouse(self, compiler, connection, **extra_context):
        return functions.Random.as_sql(
            self, compiler, connection, function="rand64", **extra_context
        )

    functions.Random.as_clickhouse = random_as_clickhouse
