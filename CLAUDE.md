# CLAUDE.md - django-clickhousedb

## Project Overview

Django database backend for ClickHouse. Package name: `django-clickhousedb` (PyPI), import name: `clickhouse_backend`. Version 1.6.0. Fork of `django-clickhouse-backend` by jayvynl, maintained by GTO Wizard.

## Build & Run

```bash
# Install in development mode
pip install -e .

# Start ClickHouse cluster (4 nodes: 2 shards x 2 replicas + HAProxy)
docker compose up -d

# Run all tests
python tests/runtests.py

# Run specific test module
python tests/runtests.py clickhouse_fields
python tests/runtests.py clickhouse_table_engine
python tests/runtests.py backends.clickhouse

# Run a single test class
python tests/runtests.py clickhouse_fields.test_arrayfield.TestArrayField
```

## Code Style

- Formatter/linter: **ruff** (line-length 88)
- Pre-commit hooks configured in `.pre-commit-config.yaml`
- No type annotations used in the codebase
- No docstring convention enforced

## Architecture Quick Reference

- **Backend entry point**: `clickhouse_backend/backend/` -- Django discovers via `ENGINE = "clickhouse_backend.backend"`
- **All user-facing imports**: `from clickhouse_backend import models` (fields, engines, functions, indexes, base model)
- **Monkey-patches**: `patch_all()` in `clickhouse_backend/patch/__init__.py` runs at backend import time, modifying Django's MigrationRecorder, Now/Random functions, and AutoField behavior
- **SQL compilers**: `clickhouse_backend/models/sql/compiler.py` -- UPDATE/DELETE generate `ALTER TABLE ... UPDATE/DELETE WHERE` (ClickHouse mutations)
- **Connection pool**: `clickhouse_backend/driver/pool.py` -- thread-safe pool, one shared physical connection per DB alias
- **ID generation**: `clickhouse_backend/idworker/snowflake.py` -- Snowflake IDs for AutoField PKs (no auto-increment in ClickHouse)
- **No transactions**: commit/rollback/savepoints are no-ops; `fake_transaction` exists only for test isolation

## Key Patterns

- Models must extend `ClickhouseModel` (not `django.db.models.Model`)
- `Meta.engine` specifies ClickHouse table engine (MergeTree, ReplicatedMergeTree, Distributed, etc.)
- `Meta.cluster` enables `ON CLUSTER` DDL
- `db_index=True` is ignored; use `Meta.indexes` with ClickHouse index types (Set, BloomFilter, MinMax, etc.)
- No foreign key / unique constraints at the database level
- Mutations are async by default; use `mutations_sync` setting for synchronous behavior

## Test Infrastructure

- Tests in `tests/` directory, run via `tests/runtests.py`
- Test settings: `tests/settings.py`
- Requires running ClickHouse cluster (`docker compose up -d`)
- `TEST.fake_transaction: True` enables test isolation with mixed DB setups
- Many tests are adapted from Django's own test suite for compatibility verification