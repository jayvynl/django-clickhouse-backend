Contributing Guide
===

Any contributions are welcomed:

- Source code.
- Documentation improvements.
- Bug reports and code reviews.

How to Contribute Source Code
---

1. Check for [open issues](https://github.com/jayvynl/django-clickhouse-backend/issues) or open a fresh issue to start a discussion around a feature idea or a bug.
2. Fork the repository on GitHub and make your changes. 
3. Write some unit tests which shows that the bug was fixed or the feature works as expected.
4. Send a pull request, the PR must pass code review and GitHub workflow before merging.

### Setup Development Environment

*This step is optional.*

1. Clone the forked repository and cd into it.

2. Install [tox](https://tox.wiki/).
   ```shell
   pip install tox
   ```

3. Start ClickHouse cluster.
   Docker and docker compose are required.
   ```shell
   docker compose up -d
   ```

4. Install dependencies.
   ```shell
   pip install -e .
   ```

### Code Style

This project use:

- [isort](https://github.com/PyCQA/isort#readme) to automate import sorting.
- [black](https://black.readthedocs.io/en/stable/) to format code.
- [flake8](https://pypi.org/project/flake8/) to lint code.

If tox is installed, code formatting can be run as:

```shell
tox -e format
```

code linting can be run as:

```shell
tox -e lint
```

### Code Conventions

As a Django derivative project, code conventions should follow Django source code whenever possible, including but not limited to:

1. Code directories arrangement.
2. Variable names.
3. Feature implementation.

For example:

- Non-aggregation SQL functions are placed in `clickhouse_backend/models/functions`, because Django place them in `django/db/models/functions`.
- Fields should be named as XXXField instead XXXType or XXXColumn.
- Index implementation should refer to Django index, not a completely new one.

### Unit Tests

Any bug fix or feature implementation must be followed by some tests. This project use [Django test suite](https://docs.djangoproject.com/en/4.2/topics/testing/) for tests.

Run tests:

```shell
python tests/runtests.py
```

If tox is installed, a list of default environments can be seen as follows:

```shell
tox -l
```

Run test for specific Python version and Django version:

```shell
tox -e py3.9-django3.2
```

run test for all supported Python version and Django version:

```shell
tox
```
