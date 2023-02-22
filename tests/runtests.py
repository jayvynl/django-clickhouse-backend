import argparse
import os
import sys

import django
from django.conf import settings
from clickhouse_backend.compat import dj32
from django.test.utils import get_runner

RUNTESTS_DIR = os.path.abspath(os.path.dirname(__file__))
SKIP_DIRS = ['unsupported']


def get_test_modules():
    """
    Scan the tests directory and yield the names of all test modules.
    """
    with os.scandir(RUNTESTS_DIR) as entries:
        for f in entries:
            if (
                "." in f.name
                or os.path.basename(f.name) in SKIP_DIRS
                or f.is_file()
                or not os.path.exists(os.path.join(f.path, "__init__.py"))
            ):
                continue
            test_module = f.name
            yield test_module


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Run the Django test suite.")
    parser.add_argument(
        "modules",
        nargs="*",
        metavar="module",
        help='Optional path(s) to test modules; e.g. "aggregation" or '
        '"aggregation.tests.AggregateTestCase.test_empty_aggregate".',
    )
    parser.add_argument(
        "-v",
        "--verbosity",
        default=1,
        type=int,
        choices=[0, 1, 2, 3],
        help="Verbosity level; 0=minimal output, 1=normal output, 2=all output",
    )
    parser.add_argument(
        "--noinput",
        action="store_false",
        dest="interactive",
        help="Tells Django to NOT prompt the user for input of any kind.",
    )
    parser.add_argument(
        "--failfast",
        action="store_true",
        help="Tells Django to stop running the test suite after first failed test.",
    )
    parser.add_argument(
        "--keepdb",
        action="store_true",
        help="Tells Django to preserve the test database between runs.",
    )
    parser.add_argument(
        "--debug-sql",
        action="store_true",
        help="Turn on the SQL query logger within tests.",
    )
    if dj32:
        from django.test.runner import default_test_processes
        parser.add_argument(
            '--parallel', nargs='?', default=0, type=int,
            const=default_test_processes(), metavar='N',
            help='Run tests using up to N parallel processes.',
        )
    else:
        from django.test.runner import parallel_type
        parser.add_argument(
            "--parallel",
            nargs="?",
            const="auto",
            default=0,
            type=parallel_type,
            metavar="N",
            help=(
                'Run tests using up to N parallel processes. Use the value "auto" '
                "to run one test process for each processor core."
            ),
        )
    options = parser.parse_args()
    options.modules = [os.path.normpath(labels) for labels in options.modules]

    os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
    modules = list(get_test_modules())
    settings.INSTALLED_APPS.extend(modules)
    django.setup()

    parallel = options.parallel
    if not dj32 and parallel in {0, "auto"}:
        # This doesn't work before django.setup() on some databases.
        from django.db import connections
        from django.test.runner import get_max_test_processes
        if all(conn.features.can_clone_databases for conn in connections.all()):
            parallel = get_max_test_processes()
        else:
            parallel = 1

    TestRunner = get_runner(settings)
    test_runner = TestRunner(
        verbosity=options.verbosity,
        noinput=options.interactive,
        failfast=options.failfast,
        keepdb=options.keepdb,
        debug_sql=options.debug_sql,
        parallel=parallel,
    )
    failures = test_runner.run_tests(options.modules or modules)
    sys.exit(bool(failures))
