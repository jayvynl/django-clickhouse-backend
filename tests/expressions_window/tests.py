import datetime
from collections import Counter
from decimal import Decimal

from django.core.exceptions import FieldError
from django.db import connection
from django.db.models import (
    Avg,
    Case,
    F,
    IntegerField,
    Max,
    Min,
    OrderBy,
    Q,
    RowRange,
    Sum,
    Value,
    ValueRange,
    When,
    Window,
)
from django.db.models.fields.json import KeyTextTransform, KeyTransform
from django.db.models.functions import (
    Cast,
    DenseRank,
    ExtractYear,
    FirstValue,
    LastValue,
    NthValue,
    Ntile,
    Rank,
    RowNumber,
    Upper,
)
from django.db.models.lookups import Exact
from django.test import TestCase, skipUnlessDBFeature
from django.test.utils import CaptureQueriesContext

from clickhouse_backend import compat

from .models import Classification, Detail, Employee


@skipUnlessDBFeature("supports_over_clause")
class WindowFunctionTests(TestCase):
    if not compat.dj_ge42:

        def assertQuerySetEqual(
            self, qs, values, transform=None, ordered=True, msg=None
        ):
            values = list(values)
            items = qs
            if transform is not None:
                items = map(transform, items)
            if not ordered:
                return self.assertDictEqual(Counter(items), Counter(values), msg=msg)
            # For example qs.iterator() could be passed as qs, but it does not
            # have 'ordered' attribute.
            if len(values) > 1 and hasattr(qs, "ordered") and not qs.ordered:
                raise ValueError(
                    "Trying to compare non-ordered queryset against more than one "
                    "ordered value."
                )
            return self.assertEqual(list(items), values, msg=msg)

    @classmethod
    def setUpTestData(cls):
        classification = Classification.objects.create()
        Employee.objects.bulk_create(
            [
                Employee(
                    name=e[0],
                    salary=e[1],
                    department=e[2],
                    hire_date=e[3],
                    age=e[4],
                    bonus=Decimal(e[1]) / 400,
                    classification=classification,
                )
                for e in [
                    ("Jones", 45000, "Accounting", datetime.datetime(2005, 11, 1), 20),
                    (
                        "Williams",
                        37000,
                        "Accounting",
                        datetime.datetime(2009, 6, 1),
                        20,
                    ),
                    ("Jenson", 45000, "Accounting", datetime.datetime(2008, 4, 1), 20),
                    ("Adams", 50000, "Accounting", datetime.datetime(2013, 7, 1), 50),
                    ("Smith", 55000, "Sales", datetime.datetime(2007, 6, 1), 30),
                    ("Brown", 53000, "Sales", datetime.datetime(2009, 9, 1), 30),
                    ("Johnson", 40000, "Marketing", datetime.datetime(2012, 3, 1), 30),
                    ("Smith", 38000, "Marketing", datetime.datetime(2009, 10, 1), 20),
                    ("Wilkinson", 60000, "IT", datetime.datetime(2011, 3, 1), 40),
                    ("Moore", 34000, "IT", datetime.datetime(2013, 8, 1), 40),
                    ("Miller", 100000, "Management", datetime.datetime(2005, 6, 1), 40),
                    ("Johnson", 80000, "Management", datetime.datetime(2005, 7, 1), 50),
                ]
            ]
        )

    def test_dense_rank(self):
        tests = [
            ExtractYear(F("hire_date")).asc(),
            F("hire_date__year").asc(),
        ]
        if compat.dj_ge41:
            tests.append("hire_date__year")
        for order_by in tests:
            with self.subTest(order_by=order_by):
                qs = Employee.objects.annotate(
                    rank=Window(expression=DenseRank(), order_by=order_by),
                )
                self.assertQuerySetEqual(
                    qs,
                    [
                        ("Jones", 45000, "Accounting", datetime.date(2005, 11, 1), 1),
                        ("Miller", 100000, "Management", datetime.date(2005, 6, 1), 1),
                        ("Johnson", 80000, "Management", datetime.date(2005, 7, 1), 1),
                        ("Smith", 55000, "Sales", datetime.date(2007, 6, 1), 2),
                        ("Jenson", 45000, "Accounting", datetime.date(2008, 4, 1), 3),
                        ("Smith", 38000, "Marketing", datetime.date(2009, 10, 1), 4),
                        ("Brown", 53000, "Sales", datetime.date(2009, 9, 1), 4),
                        ("Williams", 37000, "Accounting", datetime.date(2009, 6, 1), 4),
                        ("Wilkinson", 60000, "IT", datetime.date(2011, 3, 1), 5),
                        ("Johnson", 40000, "Marketing", datetime.date(2012, 3, 1), 6),
                        ("Moore", 34000, "IT", datetime.date(2013, 8, 1), 7),
                        ("Adams", 50000, "Accounting", datetime.date(2013, 7, 1), 7),
                    ],
                    lambda entry: (
                        entry.name,
                        entry.salary,
                        entry.department,
                        entry.hire_date,
                        entry.rank,
                    ),
                    ordered=False,
                )

    def test_department_salary(self):
        qs = Employee.objects.annotate(
            department_sum=Window(
                expression=Sum("salary"),
                partition_by=F("department"),
                order_by=[F("hire_date").asc()],
            )
        ).order_by("department", "department_sum")
        self.assertQuerySetEqual(
            qs,
            [
                ("Jones", "Accounting", 45000, 45000),
                ("Jenson", "Accounting", 45000, 90000),
                ("Williams", "Accounting", 37000, 127000),
                ("Adams", "Accounting", 50000, 177000),
                ("Wilkinson", "IT", 60000, 60000),
                ("Moore", "IT", 34000, 94000),
                ("Miller", "Management", 100000, 100000),
                ("Johnson", "Management", 80000, 180000),
                ("Smith", "Marketing", 38000, 38000),
                ("Johnson", "Marketing", 40000, 78000),
                ("Smith", "Sales", 55000, 55000),
                ("Brown", "Sales", 53000, 108000),
            ],
            lambda entry: (
                entry.name,
                entry.department,
                entry.salary,
                entry.department_sum,
            ),
        )

    def test_rank(self):
        """
        Rank the employees based on the year they're were hired. Since there
        are multiple employees hired in different years, this will contain
        gaps.
        """
        qs = Employee.objects.annotate(
            rank=Window(
                expression=Rank(),
                order_by=F("hire_date__year").asc(),
            )
        )
        self.assertQuerySetEqual(
            qs,
            [
                ("Jones", 45000, "Accounting", datetime.date(2005, 11, 1), 1),
                ("Miller", 100000, "Management", datetime.date(2005, 6, 1), 1),
                ("Johnson", 80000, "Management", datetime.date(2005, 7, 1), 1),
                ("Smith", 55000, "Sales", datetime.date(2007, 6, 1), 4),
                ("Jenson", 45000, "Accounting", datetime.date(2008, 4, 1), 5),
                ("Smith", 38000, "Marketing", datetime.date(2009, 10, 1), 6),
                ("Brown", 53000, "Sales", datetime.date(2009, 9, 1), 6),
                ("Williams", 37000, "Accounting", datetime.date(2009, 6, 1), 6),
                ("Wilkinson", 60000, "IT", datetime.date(2011, 3, 1), 9),
                ("Johnson", 40000, "Marketing", datetime.date(2012, 3, 1), 10),
                ("Moore", 34000, "IT", datetime.date(2013, 8, 1), 11),
                ("Adams", 50000, "Accounting", datetime.date(2013, 7, 1), 11),
            ],
            lambda entry: (
                entry.name,
                entry.salary,
                entry.department,
                entry.hire_date,
                entry.rank,
            ),
            ordered=False,
        )

    def test_row_number(self):
        """
        The row number window function computes the number based on the order
        in which the tuples were inserted. Depending on the backend,

        Oracle requires an ordering-clause in the Window expression.
        """
        qs = Employee.objects.annotate(
            row_number=Window(
                expression=RowNumber(),
                order_by=F("pk").asc(),
            )
        ).order_by("pk")
        self.assertQuerySetEqual(
            qs,
            [
                ("Jones", "Accounting", 1),
                ("Williams", "Accounting", 2),
                ("Jenson", "Accounting", 3),
                ("Adams", "Accounting", 4),
                ("Smith", "Sales", 5),
                ("Brown", "Sales", 6),
                ("Johnson", "Marketing", 7),
                ("Smith", "Marketing", 8),
                ("Wilkinson", "IT", 9),
                ("Moore", "IT", 10),
                ("Miller", "Management", 11),
                ("Johnson", "Management", 12),
            ],
            lambda entry: (entry.name, entry.department, entry.row_number),
        )

    def test_row_number_no_ordering(self):
        """
        The row number window function computes the number based on the order
        in which the tuples were inserted.
        """
        # Add a default ordering for consistent results across databases.
        qs = Employee.objects.annotate(
            row_number=Window(
                expression=RowNumber(),
            )
        ).order_by("pk")
        self.assertQuerySetEqual(
            qs,
            [
                ("Jones", "Accounting", 1),
                ("Williams", "Accounting", 2),
                ("Jenson", "Accounting", 3),
                ("Adams", "Accounting", 4),
                ("Smith", "Sales", 5),
                ("Brown", "Sales", 6),
                ("Johnson", "Marketing", 7),
                ("Smith", "Marketing", 8),
                ("Wilkinson", "IT", 9),
                ("Moore", "IT", 10),
                ("Miller", "Management", 11),
                ("Johnson", "Management", 12),
            ],
            lambda entry: (entry.name, entry.department, entry.row_number),
        )

    def test_avg_salary_department(self):
        qs = Employee.objects.annotate(
            avg_salary=Window(
                expression=Avg("salary"),
                order_by=F("department").asc(),
                partition_by="department",
            )
        ).order_by("department", "-salary", "name")
        self.assertQuerySetEqual(
            qs,
            [
                ("Adams", 50000, "Accounting", 44250.00),
                ("Jenson", 45000, "Accounting", 44250.00),
                ("Jones", 45000, "Accounting", 44250.00),
                ("Williams", 37000, "Accounting", 44250.00),
                ("Wilkinson", 60000, "IT", 47000.00),
                ("Moore", 34000, "IT", 47000.00),
                ("Miller", 100000, "Management", 90000.00),
                ("Johnson", 80000, "Management", 90000.00),
                ("Johnson", 40000, "Marketing", 39000.00),
                ("Smith", 38000, "Marketing", 39000.00),
                ("Smith", 55000, "Sales", 54000.00),
                ("Brown", 53000, "Sales", 54000.00),
            ],
            transform=lambda row: (
                row.name,
                row.salary,
                row.department,
                row.avg_salary,
            ),
        )

    def test_first_value(self):
        qs = Employee.objects.annotate(
            first_value=Window(
                expression=FirstValue("salary"),
                partition_by=F("department"),
                order_by=F("hire_date").asc(),
            )
        ).order_by("department", "hire_date")
        self.assertQuerySetEqual(
            qs,
            [
                ("Jones", 45000, "Accounting", datetime.date(2005, 11, 1), 45000),
                ("Jenson", 45000, "Accounting", datetime.date(2008, 4, 1), 45000),
                ("Williams", 37000, "Accounting", datetime.date(2009, 6, 1), 45000),
                ("Adams", 50000, "Accounting", datetime.date(2013, 7, 1), 45000),
                ("Wilkinson", 60000, "IT", datetime.date(2011, 3, 1), 60000),
                ("Moore", 34000, "IT", datetime.date(2013, 8, 1), 60000),
                ("Miller", 100000, "Management", datetime.date(2005, 6, 1), 100000),
                ("Johnson", 80000, "Management", datetime.date(2005, 7, 1), 100000),
                ("Smith", 38000, "Marketing", datetime.date(2009, 10, 1), 38000),
                ("Johnson", 40000, "Marketing", datetime.date(2012, 3, 1), 38000),
                ("Smith", 55000, "Sales", datetime.date(2007, 6, 1), 55000),
                ("Brown", 53000, "Sales", datetime.date(2009, 9, 1), 55000),
            ],
            lambda row: (
                row.name,
                row.salary,
                row.department,
                row.hire_date,
                row.first_value,
            ),
        )

    def test_last_value(self):
        qs = Employee.objects.annotate(
            last_value=Window(
                expression=LastValue("hire_date"),
                partition_by=F("department"),
                order_by=F("hire_date").asc(),
            )
        )
        self.assertQuerySetEqual(
            qs,
            [
                (
                    "Adams",
                    "Accounting",
                    datetime.date(2013, 7, 1),
                    50000,
                    datetime.date(2013, 7, 1),
                ),
                (
                    "Jenson",
                    "Accounting",
                    datetime.date(2008, 4, 1),
                    45000,
                    datetime.date(2008, 4, 1),
                ),
                (
                    "Jones",
                    "Accounting",
                    datetime.date(2005, 11, 1),
                    45000,
                    datetime.date(2005, 11, 1),
                ),
                (
                    "Williams",
                    "Accounting",
                    datetime.date(2009, 6, 1),
                    37000,
                    datetime.date(2009, 6, 1),
                ),
                (
                    "Moore",
                    "IT",
                    datetime.date(2013, 8, 1),
                    34000,
                    datetime.date(2013, 8, 1),
                ),
                (
                    "Wilkinson",
                    "IT",
                    datetime.date(2011, 3, 1),
                    60000,
                    datetime.date(2011, 3, 1),
                ),
                (
                    "Miller",
                    "Management",
                    datetime.date(2005, 6, 1),
                    100000,
                    datetime.date(2005, 6, 1),
                ),
                (
                    "Johnson",
                    "Management",
                    datetime.date(2005, 7, 1),
                    80000,
                    datetime.date(2005, 7, 1),
                ),
                (
                    "Johnson",
                    "Marketing",
                    datetime.date(2012, 3, 1),
                    40000,
                    datetime.date(2012, 3, 1),
                ),
                (
                    "Smith",
                    "Marketing",
                    datetime.date(2009, 10, 1),
                    38000,
                    datetime.date(2009, 10, 1),
                ),
                (
                    "Brown",
                    "Sales",
                    datetime.date(2009, 9, 1),
                    53000,
                    datetime.date(2009, 9, 1),
                ),
                (
                    "Smith",
                    "Sales",
                    datetime.date(2007, 6, 1),
                    55000,
                    datetime.date(2007, 6, 1),
                ),
            ],
            transform=lambda row: (
                row.name,
                row.department,
                row.hire_date,
                row.salary,
                row.last_value,
            ),
            ordered=False,
        )

    def test_min_department(self):
        """An alternative way to specify a query for FirstValue."""
        qs = Employee.objects.annotate(
            min_salary=Window(
                expression=Min("salary"),
                partition_by=F("department"),
                order_by=[F("salary").asc(), F("name").asc()],
            )
        ).order_by("department", "salary", "name")
        self.assertQuerySetEqual(
            qs,
            [
                ("Williams", "Accounting", 37000, 37000),
                ("Jenson", "Accounting", 45000, 37000),
                ("Jones", "Accounting", 45000, 37000),
                ("Adams", "Accounting", 50000, 37000),
                ("Moore", "IT", 34000, 34000),
                ("Wilkinson", "IT", 60000, 34000),
                ("Johnson", "Management", 80000, 80000),
                ("Miller", "Management", 100000, 80000),
                ("Smith", "Marketing", 38000, 38000),
                ("Johnson", "Marketing", 40000, 38000),
                ("Brown", "Sales", 53000, 53000),
                ("Smith", "Sales", 55000, 53000),
            ],
            lambda row: (row.name, row.department, row.salary, row.min_salary),
        )

    def test_max_per_year(self):
        """
        Find the maximum salary awarded in the same year as the
        employee was hired, regardless of the department.
        """
        qs = Employee.objects.annotate(
            max_salary_year=Window(
                expression=Max("salary"),
                order_by=ExtractYear("hire_date").asc(),
                partition_by=ExtractYear("hire_date"),
            )
        ).order_by(ExtractYear("hire_date"), "salary")
        self.assertQuerySetEqual(
            qs,
            [
                ("Jones", "Accounting", 45000, 2005, 100000),
                ("Johnson", "Management", 80000, 2005, 100000),
                ("Miller", "Management", 100000, 2005, 100000),
                ("Smith", "Sales", 55000, 2007, 55000),
                ("Jenson", "Accounting", 45000, 2008, 45000),
                ("Williams", "Accounting", 37000, 2009, 53000),
                ("Smith", "Marketing", 38000, 2009, 53000),
                ("Brown", "Sales", 53000, 2009, 53000),
                ("Wilkinson", "IT", 60000, 2011, 60000),
                ("Johnson", "Marketing", 40000, 2012, 40000),
                ("Moore", "IT", 34000, 2013, 50000),
                ("Adams", "Accounting", 50000, 2013, 50000),
            ],
            lambda row: (
                row.name,
                row.department,
                row.salary,
                row.hire_date.year,
                row.max_salary_year,
            ),
        )

    def test_nthvalue(self):
        qs = Employee.objects.annotate(
            nth_value=Window(
                expression=NthValue(expression="salary", nth=2),
                order_by=[F("hire_date").asc(), F("name").desc()],
                partition_by=F("department"),
            )
        ).order_by("department", "hire_date", "name")
        self.assertQuerySetEqual(
            qs,
            [
                ("Jones", "Accounting", datetime.date(2005, 11, 1), 45000, 0),
                ("Jenson", "Accounting", datetime.date(2008, 4, 1), 45000, 45000),
                ("Williams", "Accounting", datetime.date(2009, 6, 1), 37000, 45000),
                ("Adams", "Accounting", datetime.date(2013, 7, 1), 50000, 45000),
                ("Wilkinson", "IT", datetime.date(2011, 3, 1), 60000, 0),
                ("Moore", "IT", datetime.date(2013, 8, 1), 34000, 34000),
                ("Miller", "Management", datetime.date(2005, 6, 1), 100000, 0),
                ("Johnson", "Management", datetime.date(2005, 7, 1), 80000, 80000),
                ("Smith", "Marketing", datetime.date(2009, 10, 1), 38000, 0),
                ("Johnson", "Marketing", datetime.date(2012, 3, 1), 40000, 40000),
                ("Smith", "Sales", datetime.date(2007, 6, 1), 55000, 0),
                ("Brown", "Sales", datetime.date(2009, 9, 1), 53000, 53000),
            ],
            lambda row: (
                row.name,
                row.department,
                row.hire_date,
                row.salary,
                row.nth_value,
            ),
        )

    def test_ntile(self):
        """
        Compute the group for each of the employees across the entire company,
        based on how high the salary is for them. There are twelve employees
        so it divides evenly into four groups.
        """
        qs = Employee.objects.annotate(
            ntile=Window(
                expression=Ntile(num_buckets=4),
                order_by="-salary"
                if compat.dj_ge41
                else OrderBy(F("salary"), descending=True),
                # https://github.com/ClickHouse/ClickHouse/issues/61391
                # recent clickhouse version(24.5.3.5) ntile has a bug,
                # older version(23.6) is OK without frame.
                frame=RowRange(),
            )
        ).order_by("ntile", "-salary", "name")
        self.assertQuerySetEqual(
            qs,
            [
                ("Miller", "Management", 100000, 1),
                ("Johnson", "Management", 80000, 1),
                ("Wilkinson", "IT", 60000, 1),
                ("Smith", "Sales", 55000, 2),
                ("Brown", "Sales", 53000, 2),
                ("Adams", "Accounting", 50000, 2),
                ("Jenson", "Accounting", 45000, 3),
                ("Jones", "Accounting", 45000, 3),
                ("Johnson", "Marketing", 40000, 3),
                ("Smith", "Marketing", 38000, 4),
                ("Williams", "Accounting", 37000, 4),
                ("Moore", "IT", 34000, 4),
            ],
            lambda x: (x.name, x.department, x.salary, x.ntile),
        )

    def test_nth_returns_null(self):
        """
        Find the nth row of the data set. None is returned since there are
        fewer than 20 rows in the test data.
        """
        qs = Employee.objects.annotate(
            nth_value=Window(
                expression=NthValue("salary", nth=20), order_by=F("salary").asc()
            )
        )
        self.assertEqual(list(qs.values_list("nth_value", flat=True).distinct()), [0])

    def test_multiple_ordering(self):
        """
        Accumulate the salaries over the departments based on hire_date.
        If two people were hired on the same date in the same department, the
        ordering clause will render a different result for those people.
        """
        qs = Employee.objects.annotate(
            sum=Window(
                expression=Sum("salary"),
                partition_by="department",
                order_by=[F("hire_date").asc(), F("name").asc()],
            )
        ).order_by("department", "sum")
        self.assertQuerySetEqual(
            qs,
            [
                ("Jones", 45000, "Accounting", datetime.date(2005, 11, 1), 45000),
                ("Jenson", 45000, "Accounting", datetime.date(2008, 4, 1), 90000),
                ("Williams", 37000, "Accounting", datetime.date(2009, 6, 1), 127000),
                ("Adams", 50000, "Accounting", datetime.date(2013, 7, 1), 177000),
                ("Wilkinson", 60000, "IT", datetime.date(2011, 3, 1), 60000),
                ("Moore", 34000, "IT", datetime.date(2013, 8, 1), 94000),
                ("Miller", 100000, "Management", datetime.date(2005, 6, 1), 100000),
                ("Johnson", 80000, "Management", datetime.date(2005, 7, 1), 180000),
                ("Smith", 38000, "Marketing", datetime.date(2009, 10, 1), 38000),
                ("Johnson", 40000, "Marketing", datetime.date(2012, 3, 1), 78000),
                ("Smith", 55000, "Sales", datetime.date(2007, 6, 1), 55000),
                ("Brown", 53000, "Sales", datetime.date(2009, 9, 1), 108000),
            ],
            transform=lambda row: (
                row.name,
                row.salary,
                row.department,
                row.hire_date,
                row.sum,
            ),
        )

    def test_related_ordering_with_count(self):
        qs = Employee.objects.annotate(
            department_sum=Window(
                expression=Sum("salary"),
                partition_by=F("department"),
                order_by=["classification__code"],
            )
        )
        self.assertEqual(qs.count(), 12)

    if compat.dj_ge42:

        def test_filter(self):
            qs = Employee.objects.annotate(
                department_salary_rank=Window(
                    Rank(), partition_by="department", order_by="-salary"
                ),
                department_avg_age_diff=(
                    Window(Avg("age"), partition_by="department") - F("age")
                ),
            ).order_by("department", "name")
            # Direct window reference.
            self.assertQuerySetEqual(
                qs.filter(department_salary_rank=1),
                ["Adams", "Wilkinson", "Miller", "Johnson", "Smith"],
                lambda employee: employee.name,
            )
            # Through a combined expression containing a window.
            self.assertQuerySetEqual(
                qs.filter(department_avg_age_diff__gt=0),
                ["Jenson", "Jones", "Williams", "Miller", "Smith"],
                lambda employee: employee.name,
            )
            # Intersection of multiple windows.
            self.assertQuerySetEqual(
                qs.filter(department_salary_rank=1, department_avg_age_diff__gt=0),
                ["Miller"],
                lambda employee: employee.name,
            )
            # Union of multiple windows.
            self.assertQuerySetEqual(
                qs.filter(
                    Q(department_salary_rank=1) | Q(department_avg_age_diff__gt=0)
                ),
                [
                    "Adams",
                    "Jenson",
                    "Jones",
                    "Williams",
                    "Wilkinson",
                    "Miller",
                    "Johnson",
                    "Smith",
                    "Smith",
                ],
                lambda employee: employee.name,
            )

        def test_filter_conditional_annotation(self):
            qs = (
                Employee.objects.annotate(
                    rank=Window(Rank(), partition_by="department", order_by="-salary"),
                    case_first_rank=Case(
                        When(rank=1, then=True),
                        default=False,
                    ),
                    q_first_rank=Q(rank=1),
                )
                .order_by("name")
                .values_list("name", flat=True)
            )
            for annotation in ["case_first_rank", "q_first_rank"]:
                with self.subTest(annotation=annotation):
                    self.assertSequenceEqual(
                        qs.filter(**{annotation: True}),
                        ["Adams", "Johnson", "Miller", "Smith", "Wilkinson"],
                    )

            def test_filter_conditional_expression(self):
                qs = (
                    Employee.objects.filter(
                        Exact(
                            Window(
                                Rank(), partition_by="department", order_by="-salary"
                            ),
                            1,
                        )
                    )
                    .order_by("name")
                    .values_list("name", flat=True)
                )
                self.assertSequenceEqual(
                    qs, ["Adams", "Johnson", "Miller", "Smith", "Wilkinson"]
                )

            def test_filter_column_ref_rhs(self):
                qs = (
                    Employee.objects.annotate(
                        max_dept_salary=Window(Max("salary"), partition_by="department")
                    )
                    .filter(max_dept_salary=F("salary"))
                    .order_by("name")
                    .values_list("name", flat=True)
                )
                self.assertSequenceEqual(
                    qs, ["Adams", "Johnson", "Miller", "Smith", "Wilkinson"]
                )

            def test_filter_values(self):
                qs = (
                    Employee.objects.annotate(
                        department_salary_rank=Window(
                            Rank(), partition_by="department", order_by="-salary"
                        ),
                    )
                    .order_by("department", "name")
                    .values_list(Upper("name"), flat=True)
                )
                self.assertSequenceEqual(
                    qs.filter(department_salary_rank=1),
                    ["ADAMS", "WILKINSON", "MILLER", "JOHNSON", "SMITH"],
                )

            def test_filter_alias(self):
                qs = Employee.objects.alias(
                    department_avg_age_diff=(
                        Window(Avg("age"), partition_by="department") - F("age")
                    ),
                ).order_by("department", "name")
                self.assertQuerySetEqual(
                    qs.filter(department_avg_age_diff__gt=0),
                    ["Jenson", "Jones", "Williams", "Miller", "Smith"],
                    lambda employee: employee.name,
                )

            def test_filter_select_related(self):
                qs = (
                    Employee.objects.alias(
                        department_avg_age_diff=(
                            Window(Avg("age"), partition_by="department") - F("age")
                        ),
                    )
                    .select_related("classification")
                    .filter(department_avg_age_diff__gt=0)
                    .order_by("department", "name")
                )
                self.assertQuerySetEqual(
                    qs,
                    ["Jenson", "Jones", "Williams", "Miller", "Smith"],
                    lambda employee: employee.name,
                )
                with self.assertNumQueries(0):
                    qs[0].classification

        def test_exclude(self):
            qs = Employee.objects.annotate(
                department_salary_rank=Window(
                    Rank(), partition_by="department", order_by="-salary"
                ),
                department_avg_age_diff=(
                    Window(Avg("age"), partition_by="department") - F("age")
                ),
            ).order_by("department", "name")
            # Direct window reference.
            self.assertQuerySetEqual(
                qs.exclude(department_salary_rank__gt=1),
                ["Adams", "Wilkinson", "Miller", "Johnson", "Smith"],
                lambda employee: employee.name,
            )
            # Through a combined expression containing a window.
            self.assertQuerySetEqual(
                qs.exclude(department_avg_age_diff__lte=0),
                ["Jenson", "Jones", "Williams", "Miller", "Smith"],
                lambda employee: employee.name,
            )
            # Union of multiple windows.
            self.assertQuerySetEqual(
                qs.exclude(
                    Q(department_salary_rank__gt=1) | Q(department_avg_age_diff__lte=0)
                ),
                ["Miller"],
                lambda employee: employee.name,
            )
            # Intersection of multiple windows.
            self.assertQuerySetEqual(
                qs.exclude(
                    department_salary_rank__gt=1, department_avg_age_diff__lte=0
                ),
                [
                    "Adams",
                    "Jenson",
                    "Jones",
                    "Williams",
                    "Wilkinson",
                    "Miller",
                    "Johnson",
                    "Smith",
                    "Smith",
                ],
                lambda employee: employee.name,
            )

            def test_heterogeneous_filter(self):
                qs = (
                    Employee.objects.annotate(
                        department_salary_rank=Window(
                            Rank(), partition_by="department", order_by="-salary"
                        ),
                    )
                    .order_by("name")
                    .values_list("name", flat=True)
                )
                # Heterogeneous filter between window function and aggregates pushes
                # the WHERE clause to the QUALIFY outer query.
                self.assertSequenceEqual(
                    qs.filter(
                        department_salary_rank=1,
                        department__in=["Accounting", "Management"],
                    ),
                    ["Adams", "Miller"],
                )
                self.assertSequenceEqual(
                    qs.filter(
                        Q(department_salary_rank=1)
                        | Q(department__in=["Accounting", "Management"])
                    ),
                    [
                        "Adams",
                        "Jenson",
                        "Johnson",
                        "Johnson",
                        "Jones",
                        "Miller",
                        "Smith",
                        "Wilkinson",
                        "Williams",
                    ],
                )

        def test_limited_filter(self):
            """
            A query filtering against a window function have its limit applied
            after window filtering takes place.
            """
            self.assertQuerySetEqual(
                Employee.objects.annotate(
                    department_salary_rank=Window(
                        Rank(), partition_by="department", order_by="-salary"
                    )
                )
                .filter(department_salary_rank=1)
                .order_by("department")[0:3],
                ["Adams", "Wilkinson", "Miller"],
                lambda employee: employee.name,
            )

        def test_filter_count(self):
            with CaptureQueriesContext(connection) as ctx:
                self.assertEqual(
                    Employee.objects.annotate(
                        department_salary_rank=Window(
                            Rank(), partition_by="department", order_by="-salary"
                        )
                    )
                    .filter(department_salary_rank=1)
                    .count(),
                    5,
                )
            self.assertEqual(len(ctx.captured_queries), 1)
            sql = ctx.captured_queries[0]["sql"].lower()
            self.assertEqual(sql.count("select"), 3)
            self.assertNotIn("group by", sql)

    @skipUnlessDBFeature("supports_frame_range_fixed_distance")
    def test_range_n_preceding_and_following(self):
        qs = Employee.objects.annotate(
            sum=Window(
                expression=Sum("salary"),
                order_by=F("salary").asc(),
                partition_by="department",
                frame=ValueRange(start=-2, end=2),
            )
        )
        self.assertIn("RANGE BETWEEN 2 PRECEDING AND 2 FOLLOWING", str(qs.query))
        self.assertQuerySetEqual(
            qs,
            [
                ("Williams", 37000, "Accounting", datetime.date(2009, 6, 1), 37000),
                ("Jones", 45000, "Accounting", datetime.date(2005, 11, 1), 90000),
                ("Jenson", 45000, "Accounting", datetime.date(2008, 4, 1), 90000),
                ("Adams", 50000, "Accounting", datetime.date(2013, 7, 1), 50000),
                ("Brown", 53000, "Sales", datetime.date(2009, 9, 1), 53000),
                ("Smith", 55000, "Sales", datetime.date(2007, 6, 1), 55000),
                ("Johnson", 40000, "Marketing", datetime.date(2012, 3, 1), 40000),
                ("Smith", 38000, "Marketing", datetime.date(2009, 10, 1), 38000),
                ("Wilkinson", 60000, "IT", datetime.date(2011, 3, 1), 60000),
                ("Moore", 34000, "IT", datetime.date(2013, 8, 1), 34000),
                ("Miller", 100000, "Management", datetime.date(2005, 6, 1), 100000),
                ("Johnson", 80000, "Management", datetime.date(2005, 7, 1), 80000),
            ],
            transform=lambda row: (
                row.name,
                row.salary,
                row.department,
                row.hire_date,
                row.sum,
            ),
            ordered=False,
        )

    def test_range_unbound(self):
        """A query with RANGE BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING."""
        qs = Employee.objects.annotate(
            sum=Window(
                expression=Sum("salary"),
                partition_by="age",
                order_by=[F("age").asc()],
                frame=ValueRange(start=None, end=None),
            )
        ).order_by("department", "hire_date", "name")
        self.assertIn(
            "RANGE BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING", str(qs.query)
        )
        self.assertQuerySetEqual(
            qs,
            [
                ("Jones", "Accounting", 45000, datetime.date(2005, 11, 1), 165000),
                ("Jenson", "Accounting", 45000, datetime.date(2008, 4, 1), 165000),
                ("Williams", "Accounting", 37000, datetime.date(2009, 6, 1), 165000),
                ("Adams", "Accounting", 50000, datetime.date(2013, 7, 1), 130000),
                ("Wilkinson", "IT", 60000, datetime.date(2011, 3, 1), 194000),
                ("Moore", "IT", 34000, datetime.date(2013, 8, 1), 194000),
                ("Miller", "Management", 100000, datetime.date(2005, 6, 1), 194000),
                ("Johnson", "Management", 80000, datetime.date(2005, 7, 1), 130000),
                ("Smith", "Marketing", 38000, datetime.date(2009, 10, 1), 165000),
                ("Johnson", "Marketing", 40000, datetime.date(2012, 3, 1), 148000),
                ("Smith", "Sales", 55000, datetime.date(2007, 6, 1), 148000),
                ("Brown", "Sales", 53000, datetime.date(2009, 9, 1), 148000),
            ],
            transform=lambda row: (
                row.name,
                row.department,
                row.salary,
                row.hire_date,
                row.sum,
            ),
        )

    def test_row_range_rank(self):
        """
        A query with ROWS BETWEEN UNBOUNDED PRECEDING AND 3 FOLLOWING.
        The resulting sum is the sum of the three next (if they exist) and all
        previous rows according to the ordering clause.
        """
        qs = Employee.objects.annotate(
            sum=Window(
                expression=Sum("salary"),
                order_by=[F("hire_date").asc(), F("name").desc()],
                frame=RowRange(start=None, end=3),
            )
        ).order_by("sum", "hire_date")
        self.assertIn("ROWS BETWEEN UNBOUNDED PRECEDING AND 3 FOLLOWING", str(qs.query))
        self.assertQuerySetEqual(
            qs,
            [
                ("Miller", 100000, "Management", datetime.date(2005, 6, 1), 280000),
                ("Johnson", 80000, "Management", datetime.date(2005, 7, 1), 325000),
                ("Jones", 45000, "Accounting", datetime.date(2005, 11, 1), 362000),
                ("Smith", 55000, "Sales", datetime.date(2007, 6, 1), 415000),
                ("Jenson", 45000, "Accounting", datetime.date(2008, 4, 1), 453000),
                ("Williams", 37000, "Accounting", datetime.date(2009, 6, 1), 513000),
                ("Brown", 53000, "Sales", datetime.date(2009, 9, 1), 553000),
                ("Smith", 38000, "Marketing", datetime.date(2009, 10, 1), 603000),
                ("Wilkinson", 60000, "IT", datetime.date(2011, 3, 1), 637000),
                ("Johnson", 40000, "Marketing", datetime.date(2012, 3, 1), 637000),
                ("Adams", 50000, "Accounting", datetime.date(2013, 7, 1), 637000),
                ("Moore", 34000, "IT", datetime.date(2013, 8, 1), 637000),
            ],
            transform=lambda row: (
                row.name,
                row.salary,
                row.department,
                row.hire_date,
                row.sum,
            ),
        )

    def test_fail_update(self):
        """Window expressions can't be used in an UPDATE statement."""
        msg = (
            "Window expressions are not allowed in this query (salary=<Window: "
            "Max(Col(expressions_window_employee, expressions_window.Employee.salary)) "
            "OVER (PARTITION BY Col(expressions_window_employee, "
            "expressions_window.Employee.department))>)."
        )
        with self.assertRaisesMessage(FieldError, msg):
            Employee.objects.filter(department="Management").update(
                salary=Window(expression=Max("salary"), partition_by="department"),
            )

    def test_fail_insert(self):
        """Window expressions can't be used in an INSERT statement."""
        msg = (
            "Window expressions are not allowed in this query (salary=<Window: "
            "Sum(Value(10000), order_by=OrderBy(F(pk), descending=False)) OVER ()"
        )
        with self.assertRaisesMessage(FieldError, msg):
            Employee.objects.create(
                name="Jameson",
                department="Management",
                hire_date=datetime.date(2007, 7, 1),
                salary=Window(expression=Sum(Value(10000), order_by=F("pk").asc())),
            )

    def test_window_expression_within_subquery(self):
        subquery_qs = Employee.objects.annotate(
            highest=Window(
                FirstValue("id"),
                partition_by=F("department"),
                order_by=F("salary").desc(),
            )
        ).values("highest")
        highest_salary = Employee.objects.filter(pk__in=subquery_qs)
        self.assertCountEqual(
            highest_salary.values("department", "salary"),
            [
                {"department": "Accounting", "salary": 50000},
                {"department": "Sales", "salary": 55000},
                {"department": "Marketing", "salary": 40000},
                {"department": "IT", "salary": 60000},
                {"department": "Management", "salary": 100000},
            ],
        )

    @skipUnlessDBFeature("supports_json_field")
    def test_key_transform(self):
        Detail.objects.bulk_create(
            [
                Detail(value={"department": "IT", "name": "Smith", "salary": 37000}),
                Detail(value={"department": "IT", "name": "Nowak", "salary": 32000}),
                Detail(value={"department": "HR", "name": "Brown", "salary": 50000}),
                Detail(value={"department": "HR", "name": "Smith", "salary": 55000}),
                Detail(value={"department": "PR", "name": "Moore", "salary": 90000}),
            ]
        )
        tests = [
            (KeyTransform("department", "value"), KeyTransform("name", "value")),
            (F("value__department"), F("value__name")),
        ]
        for partition_by, order_by in tests:
            with self.subTest(partition_by=partition_by, order_by=order_by):
                qs = Detail.objects.annotate(
                    department_sum=Window(
                        expression=Sum(
                            Cast(
                                KeyTextTransform("salary", "value"),
                                output_field=IntegerField(),
                            )
                        ),
                        partition_by=[partition_by],
                        order_by=[order_by],
                    )
                ).order_by("value__department", "department_sum")
                self.assertQuerySetEqual(
                    qs,
                    [
                        ("Brown", "HR", 50000, 50000),
                        ("Smith", "HR", 55000, 105000),
                        ("Nowak", "IT", 32000, 32000),
                        ("Smith", "IT", 37000, 69000),
                        ("Moore", "PR", 90000, 90000),
                    ],
                    lambda entry: (
                        entry.value["name"],
                        entry.value["department"],
                        entry.value["salary"],
                        entry.department_sum,
                    ),
                )

    def test_invalid_start_value_range(self):
        msg = "start argument must be a negative integer, zero, or None, but got '3'."
        with self.assertRaisesMessage(ValueError, msg):
            list(
                Employee.objects.annotate(
                    test=Window(
                        expression=Sum("salary"),
                        order_by=F("hire_date").asc(),
                        frame=ValueRange(start=3),
                    )
                )
            )

    def test_invalid_end_value_range(self):
        msg = "end argument must be a positive integer, zero, or None, but got '-3'."
        with self.assertRaisesMessage(ValueError, msg):
            list(
                Employee.objects.annotate(
                    test=Window(
                        expression=Sum("salary"),
                        order_by=F("hire_date").asc(),
                        frame=ValueRange(end=-3),
                    )
                )
            )

    def test_invalid_type_end_value_range(self):
        msg = "end argument must be a positive integer, zero, or None, but got 'a'."
        with self.assertRaisesMessage(ValueError, msg):
            list(
                Employee.objects.annotate(
                    test=Window(
                        expression=Sum("salary"),
                        order_by=F("hire_date").asc(),
                        frame=ValueRange(end="a"),
                    )
                )
            )

    def test_invalid_type_start_value_range(self):
        msg = "start argument must be a negative integer, zero, or None, but got 'a'."
        with self.assertRaisesMessage(ValueError, msg):
            list(
                Employee.objects.annotate(
                    test=Window(
                        expression=Sum("salary"),
                        frame=ValueRange(start="a"),
                    )
                )
            )

    def test_invalid_type_end_row_range(self):
        msg = "end argument must be a positive integer, zero, or None, but got 'a'."
        with self.assertRaisesMessage(ValueError, msg):
            list(
                Employee.objects.annotate(
                    test=Window(
                        expression=Sum("salary"),
                        frame=RowRange(end="a"),
                    )
                )
            )

    def test_invalid_type_start_row_range(self):
        msg = "start argument must be a negative integer, zero, or None, but got 'a'."
        with self.assertRaisesMessage(ValueError, msg):
            list(
                Employee.objects.annotate(
                    test=Window(
                        expression=Sum("salary"),
                        order_by=F("hire_date").asc(),
                        frame=RowRange(start="a"),
                    )
                )
            )
