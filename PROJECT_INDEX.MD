# Project Index: django-clickhousedb

> Package: `django-clickhousedb` v1.6.0 | Author: GTO Wizard | License: MIT
> Fork of [django-clickhouse-backend](https://github.com/jayvynl/django-clickhouse-backend)

## Package Structure

```
clickhouse_backend/              # Main package (import name)
├── __init__.py                  # VERSION = (1, 6, 0, "final", 0)
├── compat.py                    # Django version compatibility shims
├── validators.py                # Custom field validators (MaxBytesValidator, etc.)
│
├── backend/                     # Django database backend (ENGINE = "clickhouse_backend.backend")
│   ├── __init__.py              # Runs patch_all() on import
│   ├── base.py                  # DatabaseWrapper - connection management, vendor="clickhouse"
│   ├── client.py                # DatabaseClient - clickhouse-client CLI wrapper
│   ├── creation.py              # DatabaseCreation - test DB create/destroy, cluster support
│   ├── features.py              # DatabaseFeatures - capability flags, test skips
│   ├── introspection.py         # DatabaseIntrospection - system.tables/columns queries
│   ├── operations.py            # DatabaseOperations - SQL helpers, date functions, EXPLAIN
│   └── schema.py                # DatabaseSchemaEditor - DDL: CREATE/ALTER TABLE, engines, indexes
│
├── driver/                      # Low-level ClickHouse connection layer
│   ├── __init__.py
│   ├── client.py                # Client - extends clickhouse_driver.client.Client
│   ├── connection.py            # Connection + Cursor - DBAPI interface with pooling
│   ├── escape.py                # escape_param() - Python types → ClickHouse SQL literals
│   ├── pool.py                  # ClickhousePool - thread-safe connection pool
│   └── types.py                 # Binary, JSON wrapper types
│
├── models/                      # ORM extensions (import from clickhouse_backend.models)
│   ├── __init__.py              # Re-exports everything: fields, engines, functions, indexes
│   ├── aggregates.py            # uniq*, anyLast, argMax
│   ├── base.py                  # ClickhouseModel, ClickhouseManager, Meta options (engine, cluster)
│   ├── engines.py               # MergeTree family, Replicated*, Distributed
│   ├── indexes.py               # Index, MinMax, Set, BloomFilter, NgrambfV1, TokenbfV1
│   ├── query.py                 # QuerySet - .prewhere(), .settings(), .explain()
│   │
│   ├── fields/                  # ClickHouse field types
│   │   ├── __init__.py          # All scalar fields: String, DateTime64, Enum, IPv4/6, Bool, etc.
│   │   ├── base.py              # FieldMixin - Nullable/LowCardinality wrapping, backend check
│   │   ├── array.py             # ArrayField - contains/overlap/any lookups, index transforms
│   │   ├── integer.py           # Int8..Int256, UInt8..UInt256 (12 field classes)
│   │   ├── json.py              # JSONField - Object('json') type
│   │   ├── map.py               # MapField - has_key/keys/values lookups, key transforms
│   │   ├── tuple.py             # TupleField - named/unnamed tuples, element transforms
│   │   └── utils.py             # Field utility helpers
│   │
│   ├── functions/               # ClickHouse SQL functions
│   │   ├── __init__.py          # Re-exports all functions
│   │   ├── base.py              # Func base class
│   │   ├── datetime.py          # toYYYYMM, toYYYYMMDD, toStartOf*, toYearWeek
│   │   ├── hashes.py            # cityHash64, sipHash*, MD5, SHA*, BLAKE3, etc.
│   │   ├── other.py             # currentDatabase, hostName, generateSerialID
│   │   ├── random.py            # Rand
│   │   └── tuples.py            # Tuple(), tupleElement()
│   │
│   └── sql/                     # SQL compiler overrides
│       ├── __init__.py
│       ├── compiler.py          # SELECT/INSERT/UPDATE/DELETE compilers, PREWHERE/SETTINGS
│       └── query.py             # Query - prewhere WhereNode, setting_info, ExplainInfo
│
├── patch/                       # Monkey-patches applied to Django internals at import time
│   ├── __init__.py              # patch_all() → patch_functions + patch_fields + patch_migrations
│   ├── functions.py             # Now → now64(), Random → rand64()
│   ├── migrations.py            # MigrationRecorder patches, distributed migration table
│   └── fields/
│       ├── __init__.py          # patch_auto_field(), patch_jsonfield()
│       └── json.py              # JSONField ClickHouse compatibility
│
├── idworker/                    # Auto-incrementing ID generation
│   ├── __init__.py              # id_worker lazy singleton (from settings.CLICKHOUSE_ID_WORKER)
│   ├── base.py                  # BaseIDWorker abstract interface
│   └── snowflake.py             # SnowflakeIDWorker - Twitter Snowflake algorithm (64-bit)
│
├── utils/
│   ├── __init__.py
│   ├── encoding.py              # Encoding utilities
│   ├── timezone.py              # Timezone helpers
│   └── version.py               # get_version() - PEP 440 version string from VERSION tuple
│
└── management/
    └── commands/
        └── inspectdb.py         # Enhanced inspectdb for ClickHouse tables
```

## Test Suite

```
tests/
├── runtests.py                  # Test runner entry point
├── settings.py                  # Test database configuration
├── dbrouters.py                 # Test database router
│
├── clickhouse_fields/           # Tests for all ClickHouse-specific field types
│   ├── test_arrayfield.py
│   ├── test_mapfield.py
│   ├── test_jsonfield.py
│   ├── test_tuplefield.py
│   └── tests.py                 # Scalar fields, enum, IP, etc.
│
├── clickhouse_functions/        # Tests for ClickHouse functions
│   ├── test_datetime.py
│   ├── test_hashes.py
│   ├── test_other.py
│   ├── test_random.py
│   └── test_tuples.py
│
├── clickhouse_queries/          # PREWHERE, SETTINGS, QuerySet extensions
├── clickhouse_table_engine/     # Engine definition and DDL tests
│   ├── test_base.py
│   ├── test_distributed.py
│   └── tests.py
│
├── backends/                    # Backend infrastructure tests
│   ├── clickhouse/
│   │   ├── test_creation.py
│   │   ├── test_driver.py
│   │   ├── test_introspection.py
│   │   ├── test_operations.py
│   │   └── tests.py
│   ├── test_ddl_references.py
│   └── test_utils.py
│
├── migrations/                  # Migration system tests (autodetector, executor, loader, graph)
│   ├── test_autodetector.py
│   ├── test_executor.py
│   ├── test_loader.py
│   ├── test_graph.py
│   └── ... (30+ migration fixture directories)
│
├── aggregates/                  # Django aggregation compatibility
├── aggregation/
├── annotations/
├── auth_tests/                  # django.contrib.auth compatibility
├── basic/
├── expressions_window/
├── inspectdb/
├── queries/
└── schema/
```

## Infrastructure

```
compose.yaml                     # 4-node ClickHouse cluster (2 shards x 2 replicas) + HAProxy
clickhouse-config/
├── node1/ .. node4/             # Per-node XML configs (macros, remote-servers, keeper)
proxy-config/
└── haproxy.cfg                  # Load balancer config for the cluster

.github/workflows/
├── base-test.yml                # Reusable test workflow
├── test-main.yml                # Tests on push to main
├── test-before-pr.yml           # Tests on PR
└── release.yml                  # PyPI release workflow

example/                         # Example Django project
├── manage.py
├── config/settings.py           # Sample DATABASES config
└── testapp/models.py            # Sample Event model with MergeTree engine
```

## Key Architecture Decisions

1. **Single import path**: Users import everything from `clickhouse_backend.models` (fields, engines, functions, indexes) -- mirrors Django's `django.db.models` pattern.

2. **Monkey-patching at import**: `patch_all()` runs when Django loads the backend, modifying `MigrationRecorder`, `Now`, `Random`, and `AutoField` behavior globally. This enables ClickHouse compatibility without requiring users to change Django internals.

3. **No transactions**: `commit()`, `rollback()`, and savepoint methods are all no-ops. `fake_transaction` mode exists only for test isolation with mixed databases.

4. **Mutations for UPDATE/DELETE**: SQL compilers generate `ALTER TABLE ... UPDATE/DELETE WHERE` instead of standard DML. For Distributed tables, these route to the local table with `ON CLUSTER`.

5. **Snowflake IDs**: Since ClickHouse has no auto-increment, the `SQLInsertCompiler` generates 64-bit Snowflake IDs for any `AutoField`-type primary key not provided at insert time.

6. **Shared connections**: `DatabaseWrapper.get_new_connection()` shares one physical connection per database alias across threads, with a thread-safe pool managing cursor-level concurrency.

7. **Migration tracking**: The `django_migrations` table uses `MergeTree` (not a relational table). Unapply sets `deleted=True` via mutation rather than deleting the row. Distributed mode creates a `Distributed()` table over local migration tables across the cluster.

## Dependencies

- `django>=3.2` (supports up to Django 6.0)
- `clickhouse-driver==0.2.9` (Python < 3.9) / `==0.2.10` (Python >= 3.9)
- No other runtime dependencies