import datetime
import re
from decimal import Decimal

from django.core.exceptions import FieldError
from django.db import connection
from django.db.models import (
    Avg,
    Case,
    Count,
    DateField,
    DateTimeField,
    DecimalField,
    Exists,
    F,
    FloatField,
    IntegerField,
    Max,
    Min,
    Q,
    StdDev,
    Sum,
    Value,
    Variance,
    When,
)
from django.db.models.expressions import Func, RawSQL
from django.db.models.functions import Cast, Coalesce, Greatest, Now, TruncHour
from django.test import TestCase
from django.test.utils import Approximate, CaptureQueriesContext
from django.utils import timezone

from clickhouse_backend import compat

from .models import Author, Book, Publisher, Store


class NowUTC(Now):
    template = "now64()"
    output_field = DateTimeField()

    def as_sql(self, compiler, connection, **extra_context):
        if connection.features.test_now_utc_template:
            extra_context["template"] = connection.features.test_now_utc_template
        return super().as_sql(compiler, connection, **extra_context)


class AggregateTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a1 = Author.objects.create(name="Adrian Holovaty", age=34)
        cls.a2 = Author.objects.create(name="Jacob Kaplan-Moss", age=35)
        cls.a3 = Author.objects.create(name="Brad Dayley", age=45)
        cls.a4 = Author.objects.create(name="James Bennett", age=29)
        cls.a5 = Author.objects.create(name="Jeffrey Forcier", age=37)
        cls.a6 = Author.objects.create(name="Paul Bissex", age=29)
        cls.a7 = Author.objects.create(name="Wesley J. Chun", age=25)
        cls.a8 = Author.objects.create(name="Peter Norvig", age=57)
        cls.a9 = Author.objects.create(name="Stuart Russell", age=46)
        cls.a1.friends.add(cls.a2, cls.a4)
        cls.a2.friends.add(cls.a1, cls.a7)
        cls.a4.friends.add(cls.a1)
        cls.a5.friends.add(cls.a6, cls.a7)
        cls.a6.friends.add(cls.a5, cls.a7)
        cls.a7.friends.add(cls.a2, cls.a5, cls.a6)
        cls.a8.friends.add(cls.a9)
        cls.a9.friends.add(cls.a8)

        cls.p1 = Publisher.objects.create(name="Apress", num_awards=3)
        cls.p2 = Publisher.objects.create(name="Sams", num_awards=1)
        cls.p3 = Publisher.objects.create(name="Prentice Hall", num_awards=7)
        cls.p4 = Publisher.objects.create(name="Morgan Kaufmann", num_awards=9)
        cls.p5 = Publisher.objects.create(name="Jonno's House of Books", num_awards=0)

        cls.b1 = Book.objects.create(
            isbn="159059725",
            name="The Definitive Guide to Django: Web Development Done Right",
            pages=447,
            rating=4.5,
            price=Decimal("30.00"),
            contact=cls.a1,
            publisher=cls.p1,
            pubdate=datetime.date(2007, 12, 6),
        )
        cls.b2 = Book.objects.create(
            isbn="067232959",
            name="Sams Teach Yourself Django in 24 Hours",
            pages=528,
            rating=3.0,
            price=Decimal("23.09"),
            contact=cls.a3,
            publisher=cls.p2,
            pubdate=datetime.date(2008, 3, 3),
        )
        cls.b3 = Book.objects.create(
            isbn="159059996",
            name="Practical Django Projects",
            pages=300,
            rating=4.0,
            price=Decimal("29.69"),
            contact=cls.a4,
            publisher=cls.p1,
            pubdate=datetime.date(2008, 6, 23),
        )
        cls.b4 = Book.objects.create(
            isbn="013235613",
            name="Python Web Development with Django",
            pages=350,
            rating=4.0,
            price=Decimal("29.69"),
            contact=cls.a5,
            publisher=cls.p3,
            pubdate=datetime.date(2008, 11, 3),
        )
        cls.b5 = Book.objects.create(
            isbn="013790395",
            name="Artificial Intelligence: A Modern Approach",
            pages=1132,
            rating=4.0,
            price=Decimal("82.80"),
            contact=cls.a8,
            publisher=cls.p3,
            pubdate=datetime.date(1995, 1, 15),
        )
        cls.b6 = Book.objects.create(
            isbn="155860191",
            name=(
                "Paradigms of Artificial Intelligence Programming: Case Studies in "
                "Common Lisp"
            ),
            pages=946,
            rating=5.0,
            price=Decimal("75.00"),
            contact=cls.a8,
            publisher=cls.p4,
            pubdate=datetime.date(1991, 10, 15),
        )
        cls.b1.authors.add(cls.a1, cls.a2)
        cls.b2.authors.add(cls.a3)
        cls.b3.authors.add(cls.a4)
        cls.b4.authors.add(cls.a5, cls.a6, cls.a7)
        cls.b5.authors.add(cls.a8, cls.a9)
        cls.b6.authors.add(cls.a8)

        s1 = Store.objects.create(
            name="Amazon.com",
            original_opening=datetime.datetime(1994, 4, 23, 9, 17, 42),
        )
        s2 = Store.objects.create(
            name="Books.com",
            original_opening=datetime.datetime(2001, 3, 15, 11, 23, 37),
        )
        s3 = Store.objects.create(
            name="Mamma and Pappa's Books",
            original_opening=datetime.datetime(1945, 4, 25, 16, 24, 14),
        )
        s1.books.add(cls.b1, cls.b2, cls.b3, cls.b4, cls.b5, cls.b6)
        s2.books.add(cls.b1, cls.b3, cls.b5, cls.b6)
        s3.books.add(cls.b3, cls.b4, cls.b6)

    def test_empty_aggregate(self):
        self.assertEqual(Author.objects.aggregate(), {})

    def test_aggregate_in_order_by(self):
        msg = (
            "Using an aggregate in order_by() without also including it in "
            "annotate() is not allowed: Avg(F(book__rating)"
        )
        with self.assertRaisesMessage(FieldError, msg):
            Author.objects.values("age").order_by(Avg("book__rating"))

    def test_single_aggregate(self):
        vals = Author.objects.aggregate(Avg("age"))
        self.assertEqual(vals, {"age__avg": Approximate(37.4, places=1)})

    def test_multiple_aggregates(self):
        vals = Author.objects.aggregate(Sum("age"), Avg("age"))
        self.assertEqual(
            vals, {"age__sum": 337, "age__avg": Approximate(37.4, places=1)}
        )

    def test_filter_aggregate(self):
        vals = Author.objects.filter(age__gt=29).aggregate(Sum("age"))
        self.assertEqual(vals, {"age__sum": 254})

    def test_related_aggregate(self):
        # Clickhouse will set missing column empty value (0 for number, empty string for text) instead of NULL
        # Avg might not work as expected in OUTER JOIN.
        # vals = Author.objects.aggregate(Avg("friends__age"))
        # self.assertEqual(vals, {"friends__age__avg": Approximate(34.07, places=2)})
        #
        # vals = Book.objects.filter(rating__lt=4.5).aggregate(Avg("authors__age"))
        # self.assertEqual(vals, {"authors__age__avg": Approximate(38.2857, places=2)})
        #
        # vals = Author.objects.filter(name__contains="a").aggregate(Avg("book__rating"))
        # self.assertEqual(vals, {"book__rating__avg": 4.0})

        vals = Book.objects.aggregate(Sum("publisher__num_awards"))
        self.assertEqual(vals, {"publisher__num_awards__sum": 30})

        vals = Publisher.objects.aggregate(Sum("book__price"))
        self.assertEqual(vals, {"book__price__sum": Decimal("270.27")})

    def test_aggregate_multi_join(self):
        vals = Store.objects.aggregate(Max("books__authors__age"))
        self.assertEqual(vals, {"books__authors__age__max": 57})

        vals = Author.objects.aggregate(Min("book__publisher__num_awards"))
        self.assertEqual(vals, {"book__publisher__num_awards__min": 1})

    def test_aggregate_alias(self):
        vals = Store.objects.filter(name="Amazon.com").aggregate(
            amazon_mean=Avg("books__rating")
        )
        self.assertEqual(vals, {"amazon_mean": Approximate(4.08, places=2)})

    def test_aggregate_transform(self):
        vals = Store.objects.aggregate(min_month=Min("original_opening__month"))
        self.assertEqual(vals, {"min_month": 3})

    # Clickhouse will set missing column empty value (0 for number, empty string for text) instead of NULL
    # Missing Date32 column will be set to 1970-01-01.
    # SELECT MIN(toYear("aggregation_book"."pubdate")) AS "min_year" FROM "aggregation_publisher" LEFT OUTER JOIN "aggregation_book" ON ("aggregation_publisher"."id" = "aggregation_book"."publisher_id")
    # def test_aggregate_join_transform(self):
    #     vals = Publisher.objects.aggregate(min_year=Min("book__pubdate__year"))
    #     self.assertEqual(vals, {"min_year": 1991})

    def test_annotate_basic(self):
        self.assertQuerysetEqual(
            Book.objects.annotate().order_by("pk"),
            [
                "The Definitive Guide to Django: Web Development Done Right",
                "Sams Teach Yourself Django in 24 Hours",
                "Practical Django Projects",
                "Python Web Development with Django",
                "Artificial Intelligence: A Modern Approach",
                "Paradigms of Artificial Intelligence Programming: Case Studies in "
                "Common Lisp",
            ],
            lambda b: b.name,
        )

        books = Book.objects.annotate(mean_age=Avg("authors__age"))
        b = books.get(pk=self.b1.pk)
        self.assertEqual(
            b.name, "The Definitive Guide to Django: Web Development Done Right"
        )
        self.assertEqual(b.mean_age, 34.5)

    def test_annotate_defer(self):
        qs = (
            Book.objects.annotate(page_sum=Sum("pages"))
            .defer("name")
            .filter(pk=self.b1.pk)
        )

        rows = [
            (
                self.b1.id,
                "159059725",
                447,
                "The Definitive Guide to Django: Web Development Done Right",
            )
        ]
        self.assertQuerysetEqual(
            qs.order_by("pk"), rows, lambda r: (r.id, r.isbn, r.page_sum, r.name)
        )

    def test_annotate_defer_select_related(self):
        qs = (
            Book.objects.select_related("contact")
            .annotate(page_sum=Sum("pages"))
            .defer("name")
            .filter(pk=self.b1.pk)
        )

        rows = [
            (
                self.b1.id,
                "159059725",
                447,
                "Adrian Holovaty",
                "The Definitive Guide to Django: Web Development Done Right",
            )
        ]
        self.assertQuerysetEqual(
            qs.order_by("pk"),
            rows,
            lambda r: (r.id, r.isbn, r.page_sum, r.contact.name, r.name),
        )

    def test_annotate_m2m(self):
        books = (
            Book.objects.filter(rating__lt=4.5)
            .annotate(Avg("authors__age"))
            .order_by("name")
        )
        self.assertQuerysetEqual(
            books,
            [
                ("Artificial Intelligence: A Modern Approach", 51.5),
                ("Practical Django Projects", 29.0),
                ("Python Web Development with Django", Approximate(30.3, places=1)),
                ("Sams Teach Yourself Django in 24 Hours", 45.0),
            ],
            lambda b: (b.name, b.authors__age__avg),
        )

        books = Book.objects.annotate(num_authors=Count("authors")).order_by("name")
        self.assertQuerysetEqual(
            books,
            [
                ("Artificial Intelligence: A Modern Approach", 2),
                (
                    "Paradigms of Artificial Intelligence Programming: Case Studies in "
                    "Common Lisp",
                    1,
                ),
                ("Practical Django Projects", 1),
                ("Python Web Development with Django", 3),
                ("Sams Teach Yourself Django in 24 Hours", 1),
                ("The Definitive Guide to Django: Web Development Done Right", 2),
            ],
            lambda b: (b.name, b.num_authors),
        )

    def test_backwards_m2m_annotate(self):
        authors = (
            Author.objects.filter(name__contains="a")
            .annotate(Avg("book__rating"))
            .order_by("name")
        )
        self.assertQuerysetEqual(
            authors,
            [
                ("Adrian Holovaty", 4.5),
                ("Brad Dayley", 3.0),
                ("Jacob Kaplan-Moss", 4.5),
                ("James Bennett", 4.0),
                ("Paul Bissex", 4.0),
                ("Stuart Russell", 4.0),
            ],
            lambda a: (a.name, a.book__rating__avg),
        )

        authors = Author.objects.annotate(num_books=Count("book")).order_by("name")
        self.assertQuerysetEqual(
            authors,
            [
                ("Adrian Holovaty", 1),
                ("Brad Dayley", 1),
                ("Jacob Kaplan-Moss", 1),
                ("James Bennett", 1),
                ("Jeffrey Forcier", 1),
                ("Paul Bissex", 1),
                ("Peter Norvig", 2),
                ("Stuart Russell", 1),
                ("Wesley J. Chun", 1),
            ],
            lambda a: (a.name, a.num_books),
        )

    def test_reverse_fkey_annotate(self):
        books = Book.objects.annotate(Sum("publisher__num_awards")).order_by("name")
        self.assertQuerysetEqual(
            books,
            [
                ("Artificial Intelligence: A Modern Approach", 7),
                (
                    "Paradigms of Artificial Intelligence Programming: Case Studies in "
                    "Common Lisp",
                    9,
                ),
                ("Practical Django Projects", 3),
                ("Python Web Development with Django", 7),
                ("Sams Teach Yourself Django in 24 Hours", 1),
                ("The Definitive Guide to Django: Web Development Done Right", 3),
            ],
            lambda b: (b.name, b.publisher__num_awards__sum),
        )

        publishers = Publisher.objects.annotate(Sum("book__price")).order_by("name")
        self.assertQuerysetEqual(
            publishers,
            [
                ("Apress", Decimal("59.69")),
                ("Jonno's House of Books", 0),
                ("Morgan Kaufmann", Decimal("75.00")),
                ("Prentice Hall", Decimal("112.49")),
                ("Sams", Decimal("23.09")),
            ],
            lambda p: (p.name, p.book__price__sum),
        )

    def test_annotate_values(self):
        books = list(
            Book.objects.filter(pk=self.b1.pk)
            .annotate(mean_age=Avg("authors__age"))
            .values()
        )
        self.assertEqual(
            books,
            [
                {
                    "contact_id": self.a1.id,
                    "id": self.b1.id,
                    "isbn": "159059725",
                    "mean_age": 34.5,
                    "name": (
                        "The Definitive Guide to Django: Web Development Done Right"
                    ),
                    "pages": 447,
                    "price": Approximate(Decimal("30")),
                    "pubdate": datetime.date(2007, 12, 6),
                    "publisher_id": self.p1.id,
                    "rating": 4.5,
                }
            ],
        )

        books = (
            Book.objects.filter(pk=self.b1.pk)
            .annotate(mean_age=Avg("authors__age"))
            .values("pk", "isbn", "mean_age")
        )
        self.assertEqual(
            list(books),
            [
                {
                    "pk": self.b1.pk,
                    "isbn": "159059725",
                    "mean_age": 34.5,
                }
            ],
        )

        books = (
            Book.objects.filter(pk=self.b1.pk)
            .annotate(mean_age=Avg("authors__age"))
            .values("name")
        )
        self.assertEqual(
            list(books),
            [{"name": "The Definitive Guide to Django: Web Development Done Right"}],
        )

        books = (
            Book.objects.filter(pk=self.b1.pk)
            .values()
            .annotate(mean_age=Avg("authors__age"))
        )
        self.assertEqual(
            list(books),
            [
                {
                    "contact_id": self.a1.id,
                    "id": self.b1.id,
                    "isbn": "159059725",
                    "mean_age": 34.5,
                    "name": (
                        "The Definitive Guide to Django: Web Development Done Right"
                    ),
                    "pages": 447,
                    "price": Approximate(Decimal("30")),
                    "pubdate": datetime.date(2007, 12, 6),
                    "publisher_id": self.p1.id,
                    "rating": 4.5,
                }
            ],
        )

        books = (
            Book.objects.values("rating")
            .annotate(n_authors=Count("authors__id"), mean_age=Avg("authors__age"))
            .order_by("rating")
        )
        self.assertEqual(
            list(books),
            [
                {
                    "rating": 3.0,
                    "n_authors": 1,
                    "mean_age": 45.0,
                },
                {
                    "rating": 4.0,
                    "n_authors": 6,
                    "mean_age": Approximate(37.16, places=1),
                },
                {
                    "rating": 4.5,
                    "n_authors": 2,
                    "mean_age": 34.5,
                },
                {
                    "rating": 5.0,
                    "n_authors": 1,
                    "mean_age": 57.0,
                },
            ],
        )

    def test_count(self):
        vals = Book.objects.aggregate(Count("rating"))
        self.assertEqual(vals, {"rating__count": 6})

    def test_count_star(self):
        with self.assertNumQueries(1) as ctx:
            Book.objects.aggregate(n=Count("*"))
        sql = ctx.captured_queries[0]["sql"]
        self.assertIn("SELECT COUNT(*) ", sql)

    def test_count_distinct_expression(self):
        aggs = Book.objects.aggregate(
            distinct_ratings=Count(
                Case(When(pages__gt=300, then="rating")), distinct=True
            ),
        )
        self.assertEqual(aggs["distinct_ratings"], 4)

    def test_distinct_on_aggregate(self):
        for aggregate, expected_result in (
            (Avg, 4.125),
            (Count, 4),
            (Sum, 16.5),
        ):
            with self.subTest(aggregate=aggregate.__name__):
                books = Book.objects.aggregate(
                    ratings=aggregate("rating", distinct=True)
                )
                self.assertEqual(books["ratings"], expected_result)

    def test_non_grouped_annotation_not_in_group_by(self):
        """
        An annotation not included in values() before an aggregate should be
        excluded from the group by clause.
        """
        qs = (
            Book.objects.annotate(xprice=F("price"))
            .filter(rating=4.0)
            .values("rating")
            .annotate(count=Count("publisher_id", distinct=True))
            .values("count", "rating")
            .order_by("count")
        )
        self.assertEqual(list(qs), [{"rating": 4.0, "count": 2}])

    def test_grouped_annotation_in_group_by(self):
        """
        An annotation included in values() before an aggregate should be
        included in the group by clause.
        """
        qs = (
            Book.objects.annotate(xprice=F("price"))
            .filter(rating=4.0)
            .values("rating", "xprice")
            .annotate(count=Count("publisher_id", distinct=True))
            .values("count", "rating")
            .order_by("count")
        )
        self.assertEqual(
            list(qs),
            [
                {"rating": 4.0, "count": 1},
                {"rating": 4.0, "count": 2},
            ],
        )

    def test_fkey_aggregate(self):
        explicit = list(Author.objects.annotate(Count("book__id")))
        implicit = list(Author.objects.annotate(Count("book")))
        self.assertCountEqual(explicit, implicit)

    def test_annotate_ordering(self):
        books = (
            Book.objects.values("rating")
            .annotate(oldest=Max("authors__age"))
            .order_by("oldest", "rating")
        )
        self.assertEqual(
            list(books),
            [
                {"rating": 4.5, "oldest": 35},
                {"rating": 3.0, "oldest": 45},
                {"rating": 4.0, "oldest": 57},
                {"rating": 5.0, "oldest": 57},
            ],
        )

        books = (
            Book.objects.values("rating")
            .annotate(oldest=Max("authors__age"))
            .order_by("-oldest", "-rating")
        )
        self.assertEqual(
            list(books),
            [
                {"rating": 5.0, "oldest": 57},
                {"rating": 4.0, "oldest": 57},
                {"rating": 3.0, "oldest": 45},
                {"rating": 4.5, "oldest": 35},
            ],
        )

    def test_aggregate_annotation(self):
        vals = Book.objects.annotate(num_authors=Count("authors__id")).aggregate(
            Avg("num_authors")
        )
        self.assertEqual(vals, {"num_authors__avg": Approximate(1.66, places=1)})

    def test_sum_distinct_aggregate(self):
        """
        Sum on a distinct() QuerySet should aggregate only the distinct items.
        """
        authors = Author.objects.filter(book__in=[self.b5, self.b6])
        self.assertEqual(authors.count(), 3)

        distinct_authors = authors.distinct()
        self.assertEqual(distinct_authors.count(), 2)

        # Selected author ages are 57 and 46
        age_sum = distinct_authors.aggregate(Sum("age"))
        self.assertEqual(age_sum["age__sum"], 103)

    def test_filtering(self):
        p = Publisher.objects.create(name="Expensive Publisher", num_awards=0)
        Book.objects.create(
            name="ExpensiveBook1",
            pages=1,
            isbn="111",
            rating=3.5,
            price=Decimal("1000"),
            publisher=p,
            contact_id=self.a1.id,
            pubdate=datetime.date(2008, 12, 1),
        )
        Book.objects.create(
            name="ExpensiveBook2",
            pages=1,
            isbn="222",
            rating=4.0,
            price=Decimal("1000"),
            publisher=p,
            contact_id=self.a1.id,
            pubdate=datetime.date(2008, 12, 2),
        )
        Book.objects.create(
            name="ExpensiveBook3",
            pages=1,
            isbn="333",
            rating=4.5,
            price=Decimal("35"),
            publisher=p,
            contact_id=self.a1.id,
            pubdate=datetime.date(2008, 12, 3),
        )

        publishers = (
            Publisher.objects.annotate(num_books=Count("book__id"))
            .filter(num_books__gt=1)
            .order_by("pk")
        )
        self.assertQuerysetEqual(
            publishers,
            ["Apress", "Prentice Hall", "Expensive Publisher"],
            lambda p: p.name,
        )

        publishers = Publisher.objects.filter(book__price__lt=Decimal("40.0")).order_by(
            "pk"
        )
        self.assertQuerysetEqual(
            publishers,
            [
                "Apress",
                "Apress",
                "Sams",
                "Prentice Hall",
                "Expensive Publisher",
            ],
            lambda p: p.name,
        )

        publishers = (
            Publisher.objects.annotate(num_books=Count("book__id"))
            .filter(num_books__gt=1, book__price__lt=Decimal("40.0"))
            .order_by("pk")
        )
        self.assertQuerysetEqual(
            publishers,
            ["Apress", "Prentice Hall", "Expensive Publisher"],
            lambda p: p.name,
        )

        publishers = (
            Publisher.objects.filter(book__price__lt=Decimal("40.0"))
            .annotate(num_books=Count("book__id"))
            .filter(num_books__gt=1)
            .order_by("pk")
        )
        self.assertQuerysetEqual(publishers, ["Apress"], lambda p: p.name)

        publishers = Publisher.objects.annotate(num_books=Count("book")).filter(
            num_books__isnull=True
        )
        self.assertEqual(len(publishers), 0)

    def test_annotation(self):
        vals = Author.objects.filter(pk=self.a1.pk).aggregate(Count("friends__id"))
        self.assertEqual(vals, {"friends__id__count": 2})

        books = (
            Book.objects.annotate(num_authors=Count("authors__name"))
            .filter(num_authors__exact=2)
            .order_by("pk")
        )
        self.assertQuerysetEqual(
            books,
            [
                "The Definitive Guide to Django: Web Development Done Right",
                "Artificial Intelligence: A Modern Approach",
            ],
            lambda b: b.name,
        )

        publishers = (
            Publisher.objects.annotate(num_books=Count("book__id"))
            .filter(num_books__gt=1)
            .order_by("pk")
        )
        self.assertQuerysetEqual(
            publishers, ["Apress", "Prentice Hall"], lambda p: p.name
        )

        publishers = (
            Publisher.objects.filter(book__price__lt=Decimal("40.0"))
            .annotate(num_books=Count("book__id"))
            .filter(num_books__gt=1)
        )
        self.assertQuerysetEqual(publishers, ["Apress"], lambda p: p.name)

        books = Book.objects.annotate(num_authors=Count("authors__id")).filter(
            authors__name__contains="Norvig", num_authors__gt=1
        )
        self.assertQuerysetEqual(
            books, ["Artificial Intelligence: A Modern Approach"], lambda b: b.name
        )

    def test_more_aggregation(self):
        a = Author.objects.get(name__contains="Norvig")
        b = Book.objects.get(name__contains="Done Right")
        b.authors.add(a)
        b.save()

        vals = (
            Book.objects.annotate(num_authors=Count("authors__id"))
            .filter(authors__name__contains="Norvig", num_authors__gt=1)
            .aggregate(Avg("rating"))
        )
        self.assertEqual(vals, {"rating__avg": 4.25})

    def test_annotate_values_list(self):
        books = (
            Book.objects.filter(pk=self.b1.pk)
            .annotate(mean_age=Avg("authors__age"))
            .values_list("pk", "isbn", "mean_age")
        )
        self.assertEqual(list(books), [(self.b1.id, "159059725", 34.5)])

        books = (
            Book.objects.filter(pk=self.b1.pk)
            .annotate(mean_age=Avg("authors__age"))
            .values_list("isbn")
        )
        self.assertEqual(list(books), [("159059725",)])

        books = (
            Book.objects.filter(pk=self.b1.pk)
            .annotate(mean_age=Avg("authors__age"))
            .values_list("mean_age")
        )
        self.assertEqual(list(books), [(34.5,)])

        books = (
            Book.objects.filter(pk=self.b1.pk)
            .annotate(mean_age=Avg("authors__age"))
            .values_list("mean_age", flat=True)
        )
        self.assertEqual(list(books), [34.5])

        books = (
            Book.objects.values_list("price")
            .annotate(count=Count("price"))
            .order_by("-count", "price")
        )
        self.assertEqual(
            list(books),
            [
                (Decimal("29.69"), 2),
                (Decimal("23.09"), 1),
                (Decimal("30"), 1),
                (Decimal("75"), 1),
                (Decimal("82.8"), 1),
            ],
        )

    def test_dates_with_aggregation(self):
        """
        .dates() returns a distinct set of dates when applied to a
        QuerySet with aggregation.

        Refs #18056. Previously, .dates() would return distinct (date_kind,
        aggregation) sets, in this case (year, num_authors), so 2008 would be
        returned twice because there are books from 2008 with a different
        number of authors.
        """
        dates = Book.objects.annotate(num_authors=Count("authors")).dates(
            "pubdate", "year"
        )
        self.assertSequenceEqual(
            dates,
            [
                datetime.date(1991, 1, 1),
                datetime.date(1995, 1, 1),
                datetime.date(2007, 1, 1),
                datetime.date(2008, 1, 1),
            ],
        )

    def test_values_aggregation(self):
        # Refs #20782
        max_rating = Book.objects.values("rating").aggregate(max_rating=Max("rating"))
        self.assertEqual(max_rating["max_rating"], 5)
        max_books_per_rating = (
            Book.objects.values("rating")
            .annotate(books_per_rating=Count("id"))
            .aggregate(Max("books_per_rating"))
        )
        self.assertEqual(max_books_per_rating, {"books_per_rating__max": 3})

    def test_ticket17424(self):
        """
        Doing exclude() on a foreign model after annotate() doesn't crash.
        """
        all_books = list(Book.objects.values_list("pk", flat=True).order_by("pk"))
        annotated_books = Book.objects.order_by("pk").annotate(one=Count("id"))

        # The value doesn't matter, we just need any negative
        # constraint on a related model that's a noop.
        excluded_books = annotated_books.exclude(publisher__name="__UNLIKELY_VALUE__")

        # Try to generate query tree
        str(excluded_books.query)

        self.assertQuerysetEqual(excluded_books, all_books, lambda x: x.pk)

        # Check internal state
        self.assertIsNone(annotated_books.query.alias_map["aggregation_book"].join_type)
        self.assertIsNone(excluded_books.query.alias_map["aggregation_book"].join_type)

    def test_ticket12886(self):
        """
        Aggregation over sliced queryset works correctly.
        """
        qs = Book.objects.order_by("-rating")[0:3]
        vals = qs.aggregate(average_top3_rating=Avg("rating"))["average_top3_rating"]
        self.assertAlmostEqual(vals, 4.5, places=2)

    def test_ticket11881(self):
        """
        Subqueries do not needlessly contain ORDER BY, SELECT FOR UPDATE or
        select_related() stuff.
        """
        qs = (
            Book.objects.select_for_update()
            .order_by("pk")
            .select_related("publisher")
            .annotate(max_pk=Max("pk"))
        )
        with CaptureQueriesContext(connection) as captured_queries:
            qs.aggregate(avg_pk=Avg("max_pk"))
            self.assertEqual(len(captured_queries), 1)
            qstr = captured_queries[0]["sql"].lower()
            self.assertNotIn("for update", qstr)
            forced_ordering = connection.ops.force_no_ordering()
            if forced_ordering:
                # If the backend needs to force an ordering we make sure it's
                # the only "ORDER BY" clause present in the query.
                self.assertEqual(
                    re.findall(r"order by (\w+)", qstr),
                    [", ".join(f[1][0] for f in forced_ordering).lower()],
                )
            else:
                self.assertNotIn("order by", qstr)
            self.assertEqual(qstr.count(" join "), 0)

    def test_decimal_max_digits_has_no_effect(self):
        Book.objects.all().delete()
        a1 = Author.objects.first()
        p1 = Publisher.objects.first()
        thedate = timezone.now()
        for i in range(10):
            Book.objects.create(
                isbn="abcde{}".format(i),
                name="none",
                pages=10,
                rating=4.0,
                price=9999.98,
                contact=a1,
                publisher=p1,
                pubdate=thedate,
            )

        book = Book.objects.aggregate(price_sum=Sum("price"))
        self.assertEqual(book["price_sum"], Decimal("99999.80"))

    def test_nonaggregate_aggregation_throws(self):
        with self.assertRaisesMessage(TypeError, "fail is not an aggregate expression"):
            Book.objects.aggregate(fail=F("price"))

    def test_nonfield_annotation(self):
        book = Book.objects.annotate(val=Max(Value(2))).first()
        self.assertEqual(book.val, 2)
        book = Book.objects.annotate(
            val=Max(Value(2), output_field=IntegerField())
        ).first()
        self.assertEqual(book.val, 2)
        book = Book.objects.annotate(val=Max(2, output_field=IntegerField())).first()
        self.assertEqual(book.val, 2)

    def test_aggregation_expressions(self):
        a1 = Author.objects.aggregate(av_age=Sum("age") / Count("*"))
        a2 = Author.objects.aggregate(av_age=Sum("age") / Count("age"))
        a3 = Author.objects.aggregate(av_age=Avg("age"))
        self.assertEqual(a1, {"av_age": 37})
        self.assertEqual(a2, {"av_age": 37})
        self.assertEqual(a3, {"av_age": Approximate(37.4, places=1)})

    def test_avg_decimal_field(self):
        v = Book.objects.filter(rating=4).aggregate(avg_price=(Avg("price")))[
            "avg_price"
        ]
        self.assertIsInstance(v, Decimal)
        self.assertEqual(v, Approximate(Decimal("47.39"), places=2))

    def test_order_of_precedence(self):
        p1 = Book.objects.filter(rating=4).aggregate(avg_price=(Avg("price") + 2) * 3)
        self.assertEqual(p1, {"avg_price": Approximate(Decimal("148.18"), places=2)})

        p2 = Book.objects.filter(rating=4).aggregate(avg_price=Avg("price") + 2 * 3)
        self.assertEqual(p2, {"avg_price": Approximate(Decimal("53.39"), places=2)})

    def test_combine_different_types(self):
        if compat.dj_ge41:
            msg = (
                "Cannot infer type of '+' expression involving these types: FloatField, "
                "DecimalField. You must set output_field."
            )
        else:
            msg = (
                "Expression contains mixed types: FloatField, DecimalField. "
                "You must set output_field."
            )
        qs = Book.objects.annotate(sums=Sum("rating") + Sum("pages") + Sum("price"))
        with self.assertRaisesMessage(FieldError, msg):
            qs.first()
        with self.assertRaisesMessage(FieldError, msg):
            qs.first()

        b1 = Book.objects.annotate(
            sums=Sum(F("rating") + F("pages") + F("price"), output_field=IntegerField())
        ).get(pk=self.b4.pk)
        self.assertEqual(b1.sums, 383)

        b2 = Book.objects.annotate(
            sums=Sum(F("rating") + F("pages") + F("price"), output_field=FloatField())
        ).get(pk=self.b4.pk)
        self.assertEqual(b2.sums, 383.69)

        b3 = Book.objects.annotate(
            sums=Sum(F("rating") + F("pages") + F("price"), output_field=DecimalField())
        ).get(pk=self.b4.pk)
        self.assertEqual(b3.sums, Approximate(Decimal("383.69"), places=2))

    def test_complex_aggregations_require_kwarg(self):
        with self.assertRaisesMessage(
            TypeError, "Complex annotations require an alias"
        ):
            Author.objects.annotate(Sum(F("age") + F("friends__age")))
        with self.assertRaisesMessage(TypeError, "Complex aggregates require an alias"):
            Author.objects.aggregate(Sum("age") / Count("age"))
        with self.assertRaisesMessage(TypeError, "Complex aggregates require an alias"):
            Author.objects.aggregate(Sum(1))

    def test_aggregate_over_complex_annotation(self):
        qs = Author.objects.annotate(combined_ages=Sum(F("age") + F("friends__age")))

        age = qs.aggregate(max_combined_age=Max("combined_ages"))
        self.assertEqual(age["max_combined_age"], 176)

        age = qs.aggregate(max_combined_age_doubled=Max("combined_ages") * 2)
        self.assertEqual(age["max_combined_age_doubled"], 176 * 2)

        age = qs.aggregate(
            max_combined_age_doubled=Max("combined_ages") + Max("combined_ages")
        )
        self.assertEqual(age["max_combined_age_doubled"], 176 * 2)

        age = qs.aggregate(
            max_combined_age_doubled=Max("combined_ages") + Max("combined_ages"),
            sum_combined_age=Sum("combined_ages"),
        )
        self.assertEqual(age["max_combined_age_doubled"], 176 * 2)
        # Clickhouse will set missing column empty value (0 for number, empty string for text) instead of NULL
        # age["sum_combined_age"] = 999 because author without friends is also included.
        # self.assertEqual(age["sum_combined_age"], 954)

        age = qs.aggregate(
            max_combined_age_doubled=Max("combined_ages") + Max("combined_ages"),
            sum_combined_age_doubled=Sum("combined_ages") + Sum("combined_ages"),
        )
        self.assertEqual(age["max_combined_age_doubled"], 176 * 2)
        # self.assertEqual(age["sum_combined_age_doubled"], 954 * 2)

    def test_values_annotation_with_expression(self):
        # ensure the F() is promoted to the group by clause
        qs = Author.objects.values("name").annotate(another_age=Sum("age") + F("age"))
        a = qs.get(name="Adrian Holovaty")
        self.assertEqual(a["another_age"], 68)

        qs = qs.annotate(friend_count=Count("friends"))
        a = qs.get(name="Adrian Holovaty")
        self.assertEqual(a["friend_count"], 2)

        qs = (
            qs.annotate(combined_age=Sum("age") + F("friends__age"))
            .filter(name="Adrian Holovaty")
            .order_by("-combined_age")
        )
        self.assertEqual(
            list(qs),
            [
                {
                    "name": "Adrian Holovaty",
                    "another_age": 68,
                    "friend_count": 1,
                    "combined_age": 69,
                },
                {
                    "name": "Adrian Holovaty",
                    "another_age": 68,
                    "friend_count": 1,
                    "combined_age": 63,
                },
            ],
        )

        vals = qs.values("name", "combined_age")
        self.assertEqual(
            list(vals),
            [
                {"name": "Adrian Holovaty", "combined_age": 69},
                {"name": "Adrian Holovaty", "combined_age": 63},
            ],
        )

    def test_annotate_values_aggregate(self):
        alias_age = (
            Author.objects.annotate(age_alias=F("age"))
            .values(
                "age_alias",
            )
            .aggregate(sum_age=Sum("age_alias"))
        )

        age = Author.objects.values("age").aggregate(sum_age=Sum("age"))

        self.assertEqual(alias_age["sum_age"], age["sum_age"])

    def test_annotate_over_annotate(self):
        author = (
            Author.objects.annotate(age_alias=F("age"))
            .annotate(sum_age=Sum("age_alias"))
            .get(name="Adrian Holovaty")
        )

        other_author = Author.objects.annotate(sum_age=Sum("age")).get(
            name="Adrian Holovaty"
        )

        self.assertEqual(author.sum_age, other_author.sum_age)

    def test_annotated_aggregate_over_annotated_aggregate(self):
        with self.assertRaisesMessage(
            FieldError, "Cannot compute Sum('id__max'): 'id__max' is an aggregate"
        ):
            Book.objects.annotate(Max("id")).annotate(Sum("id__max"))

        class MyMax(Max):
            arity = None

            def as_sql(self, compiler, connection):
                self.set_source_expressions(self.get_source_expressions()[0:1])
                return super().as_sql(compiler, connection)

        with self.assertRaisesMessage(
            FieldError, "Cannot compute Max('id__max'): 'id__max' is an aggregate"
        ):
            Book.objects.annotate(Max("id")).annotate(my_max=MyMax("id__max", "price"))

    def test_add_implementation(self):
        class MySum(Sum):
            pass

        # test completely changing how the output is rendered
        def lower_case_function_override(self, compiler, connection):
            sql, params = compiler.compile(self.source_expressions[0])
            substitutions = {
                "function": self.function.lower(),
                "expressions": sql,
                "distinct": "",
            }
            substitutions.update(self.extra)
            return self.template % substitutions, params

        setattr(MySum, "as_" + connection.vendor, lower_case_function_override)

        qs = Book.objects.annotate(
            sums=MySum(
                F("rating") + F("pages") + Cast("price", FloatField()),
                output_field=IntegerField(),
            )
        )
        self.assertEqual(str(qs.query).count("sum("), 1)
        b1 = qs.get(pk=self.b4.pk)
        self.assertEqual(b1.sums, 383)

        # test changing the dict and delegating
        def lower_case_function_super(self, compiler, connection):
            self.extra["function"] = self.function.lower()
            return super(MySum, self).as_sql(compiler, connection)

        setattr(MySum, "as_" + connection.vendor, lower_case_function_super)

        qs = Book.objects.annotate(
            sums=MySum(
                F("rating") + F("pages") + Cast("price", FloatField()),
                output_field=IntegerField(),
            )
        )
        self.assertEqual(str(qs.query).count("sum("), 1)
        b1 = qs.get(pk=self.b4.pk)
        self.assertEqual(b1.sums, 383)

        # test overriding all parts of the template
        def be_evil(self, compiler, connection):
            substitutions = {"function": "MAX", "expressions": "2", "distinct": ""}
            substitutions.update(self.extra)
            return self.template % substitutions, ()

        setattr(MySum, "as_" + connection.vendor, be_evil)

        qs = Book.objects.annotate(
            sums=MySum(
                F("rating") + F("pages") + Cast("price", FloatField()),
                output_field=IntegerField(),
            )
        )
        self.assertEqual(str(qs.query).count("MAX("), 1)
        b1 = qs.get(pk=self.b4.pk)
        self.assertEqual(b1.sums, 2)

    def test_complex_values_aggregation(self):
        max_rating = Book.objects.values("rating").aggregate(
            double_max_rating=Max("rating") + Max("rating")
        )
        self.assertEqual(max_rating["double_max_rating"], 5 * 2)

        max_books_per_rating = (
            Book.objects.values("rating")
            .annotate(books_per_rating=Count("id") + 5)
            .aggregate(Max("books_per_rating"))
        )
        self.assertEqual(max_books_per_rating, {"books_per_rating__max": 3 + 5})

    def test_expression_on_aggregation(self):
        qs = (
            Publisher.objects.annotate(
                price_or_median=Greatest(
                    Avg("book__rating", output_field=DecimalField()), Avg("book__price")
                )
            )
            .filter(price_or_median__gte=F("num_awards"))
            .order_by("num_awards")
        )
        self.assertQuerysetEqual(qs, [0, 1, 3, 7, 9], lambda v: v.num_awards)

        qs2 = (
            Publisher.objects.annotate(
                rating_or_num_awards=Greatest(
                    Avg("book__rating"), F("num_awards"), output_field=FloatField()
                )
            )
            .filter(rating_or_num_awards__gt=F("num_awards"))
            .order_by("num_awards")
        )
        self.assertQuerysetEqual(qs2, [1, 3], lambda v: v.num_awards)

    def test_arguments_must_be_expressions(self):
        msg = "QuerySet.aggregate() received non-expression(s): %s."
        with self.assertRaisesMessage(TypeError, msg % FloatField()):
            Book.objects.aggregate(FloatField())
        with self.assertRaisesMessage(TypeError, msg % True):
            Book.objects.aggregate(is_book=True)
        with self.assertRaisesMessage(
            TypeError, msg % ", ".join([str(FloatField()), "True"])
        ):
            Book.objects.aggregate(FloatField(), Avg("price"), is_book=True)

    # CH does not support correlated subquery.
    # https://github.com/ClickHouse/ClickHouse/issues/7872
    # def test_aggregation_subquery_annotation(self):
    #     """Subquery annotations are excluded from the GROUP BY if they are
    #     not explicitly grouped against."""
    #     latest_book_pubdate_qs = (
    #         Book.objects.filter(publisher=OuterRef("pk"))
    #         .order_by("-pubdate")
    #         .values("pubdate")[:1]
    #     )
    #     publisher_qs = Publisher.objects.annotate(
    #         latest_book_pubdate=Subquery(latest_book_pubdate_qs),
    #     ).annotate(count=Count("book"))
    #     with self.assertNumQueries(1) as ctx:
    #         list(publisher_qs)
    #     self.assertEqual(ctx[0]["sql"].count("SELECT"), 2)
    #     # The GROUP BY should not be by alias either.
    #     self.assertEqual(ctx[0]["sql"].lower().count("latest_book_pubdate"), 1)

    if compat.dj_ge41:

        def test_aggregation_filter_exists(self):
            publishers_having_more_than_one_book_qs = (
                Book.objects.values("publisher")
                .annotate(cnt=Count("isbn"))
                .filter(cnt__gt=1)
            )
            query = publishers_having_more_than_one_book_qs.query.exists("default")
            _, _, group_by = query.get_compiler(connection=connection).pre_sql_setup()
            self.assertEqual(len(group_by), 1)

    def test_aggregation_order_by_not_selected_annotation_values(self):
        result_asc = [
            self.b4.pk,
            self.b3.pk,
            self.b1.pk,
            self.b2.pk,
            self.b5.pk,
            self.b6.pk,
        ]
        result_desc = result_asc[::-1]
        tests = [
            ("min_related_age", result_asc),
            ("-min_related_age", result_desc),
            (F("min_related_age"), result_asc),
            (F("min_related_age").asc(), result_asc),
            (F("min_related_age").desc(), result_desc),
        ]
        for ordering, expected_result in tests:
            with self.subTest(ordering=ordering):
                books_qs = (
                    Book.objects.annotate(
                        min_age=Min("authors__age"),
                    )
                    .annotate(
                        min_related_age=Coalesce("min_age", "contact__age"),
                    )
                    .order_by(ordering)
                    .values_list("pk", flat=True)
                )
                self.assertEqual(list(books_qs), expected_result)

    if compat.dj_ge41:

        def test_filter_in_subquery_or_aggregation(self):
            """
            Filtering against an aggregate requires the usage of the HAVING clause.

            If such a filter is unionized to a non-aggregate one the latter will
            also need to be moved to the HAVING clause and have its grouping
            columns used in the GROUP BY.

            When this is done with a subquery the specialized logic in charge of
            using outer reference columns to group should be used instead of the
            subquery itself as the latter might return multiple rows.
            """
            authors = Author.objects.annotate(
                Count("book"),
            ).filter(Q(book__count__gt=0) | Q(pk__in=Book.objects.values("authors")))
            self.assertCountEqual(authors, Author.objects.all())

    def test_aggregation_random_ordering(self):
        """Random() is not included in the GROUP BY when used for ordering."""
        authors = Author.objects.annotate(contact_count=Count("book")).order_by("?")
        self.assertQuerysetEqual(
            authors,
            [
                ("Adrian Holovaty", 1),
                ("Jacob Kaplan-Moss", 1),
                ("Brad Dayley", 1),
                ("James Bennett", 1),
                ("Jeffrey Forcier", 1),
                ("Paul Bissex", 1),
                ("Wesley J. Chun", 1),
                ("Stuart Russell", 1),
                ("Peter Norvig", 2),
            ],
            lambda a: (a.name, a.contact_count),
            ordered=False,
        )

    if compat.dj_ge4:

        def test_empty_result_optimization(self):
            with self.assertNumQueries(0):
                self.assertEqual(
                    Publisher.objects.none().aggregate(
                        sum_awards=Sum("num_awards"),
                        books_count=Count("book"),
                    ),
                    {
                        "sum_awards": None,
                        "books_count": 0,
                    },
                )
            # Expression without empty_result_set_value forces queries to be
            # executed even if they would return an empty result set.
            raw_books_count = Func("book", function="COUNT")
            raw_books_count.contains_aggregate = True
            with self.assertNumQueries(1):
                self.assertEqual(
                    Publisher.objects.none().aggregate(
                        sum_awards=Sum("num_awards"),
                        books_count=raw_books_count,
                    ),
                    {
                        "sum_awards": 0,
                        "books_count": 0,
                    },
                )

        def test_coalesced_empty_result_set(self):
            with self.assertNumQueries(0):
                self.assertEqual(
                    Publisher.objects.none().aggregate(
                        sum_awards=Coalesce(Sum("num_awards"), 0),
                    )["sum_awards"],
                    0,
                )
            # Multiple expressions.
            with self.assertNumQueries(0):
                self.assertEqual(
                    Publisher.objects.none().aggregate(
                        sum_awards=Coalesce(Sum("num_awards"), None, 0),
                    )["sum_awards"],
                    0,
                )
            # Nested coalesce.
            with self.assertNumQueries(0):
                self.assertEqual(
                    Publisher.objects.none().aggregate(
                        sum_awards=Coalesce(Coalesce(Sum("num_awards"), None), 0),
                    )["sum_awards"],
                    0,
                )
            # Expression coalesce.
            with self.assertNumQueries(1):
                self.assertIsInstance(
                    Store.objects.none().aggregate(
                        latest_opening=Coalesce(
                            Max("original_opening"),
                            RawSQL("now64()", []),
                        ),
                    )["latest_opening"],
                    datetime.datetime,
                )

        def test_aggregation_default_unsupported_by_count(self):
            msg = "Count does not allow default."
            with self.assertRaisesMessage(TypeError, msg):
                Count("age", default=0)

        # Clickhouse aggregation function is resolved to nan in empty rows.
        def test_aggregation_default_unset(self):
            for Aggregate in [Max, Min, Sum]:
                with self.subTest(Aggregate):
                    result = Author.objects.filter(age__gt=100).aggregate(
                        value=Aggregate("age"),
                    )
                    self.assertEqual(result["value"], 0)

            for Aggregate in [Avg, StdDev, Variance]:
                with self.subTest(Aggregate):
                    result = Author.objects.filter(age__gt=100).aggregate(
                        value=Aggregate("age"),
                    )
                    self.assertEqual(str(result["value"]), "nan")

        # Clickhouse aggregation function is resolved to nan in empty rows.
        # def test_aggregation_default_zero(self):
        #     for Aggregate in [Avg, Max, Min, StdDev, Sum, Variance]:
        #         with self.subTest(Aggregate):
        #             result = Author.objects.filter(age__gt=100).aggregate(
        #                 value=Aggregate("age", default=0),
        #             )
        #             self.assertEqual(result["value"], 0)

        # Clickhouse aggregation function is resolved to nan in empty rows.
        # def test_aggregation_default_integer(self):
        #     for Aggregate in [Avg, Max, Min, StdDev, Sum, Variance]:
        #         with self.subTest(Aggregate):
        #             result = Author.objects.filter(age__gt=100).aggregate(
        #                 value=Aggregate("age", default=21),
        #             )
        #             self.assertEqual(result["value"], 21)

        # Clickhouse aggregation function is resolved to nan in empty rows.
        # def test_aggregation_default_expression(self):
        #     for Aggregate in [Avg, Max, Min, StdDev, Sum, Variance]:
        #         with self.subTest(Aggregate):
        #             result = Author.objects.filter(age__gt=100).aggregate(
        #                 value=Aggregate("age", default=Value(5) * Value(7)),
        #             )
        #             self.assertEqual(result["value"], 35)

        # Clickhouse will set missing column empty value (0 for number, empty string for text) instead of NULL
        # So Count("book") resolve to 1 in a missing LEFT OUTER JOIN match, not 0
        # def test_aggregation_default_group_by(self):
        #     qs = (
        #         Publisher.objects.values("name")
        #         .annotate(
        #             books=Count("book"),
        #             pages=Sum("book__pages", default=0),
        #         )
        #         .filter(books=0)
        #     )
        #     self.assertSequenceEqual(
        #         qs,
        #         [{"name": "Jonno's House of Books", "books": 0, "pages": 0}],
        #     )

        # Clickhouse will set missing column empty value (0 for number, empty string for text) instead of NULL
        # So default=2.5 have no effect on missing match.
        # def test_aggregation_default_compound_expression(self):
        #     # Scale rating to a percentage; default to 50% if no books published.
        #     formula = Avg("book__rating", default=2.5) * 20.0
        #     queryset = Publisher.objects.annotate(rating=formula).order_by("name")
        #     self.assertSequenceEqual(
        #         queryset.values("name", "rating"),
        #         [
        #             {"name": "Apress", "rating": 85.0},
        #             {"name": "Jonno's House of Books", "rating": 50.0},
        #             {"name": "Morgan Kaufmann", "rating": 100.0},
        #             {"name": "Prentice Hall", "rating": 80.0},
        #             {"name": "Sams", "rating": 60.0},
        #         ],
        #     )

        def test_aggregation_default_using_date_from_python(self):
            expr = Min("book__pubdate", default=datetime.date(1970, 1, 1))
            if connection.vendor == "mysql":
                # Workaround for #30224 for MySQL & MariaDB.
                expr.default = Cast(expr.default, DateField())
            queryset = Publisher.objects.annotate(earliest_pubdate=expr).order_by(
                "name"
            )
            self.assertSequenceEqual(
                queryset.values("name", "earliest_pubdate"),
                [
                    {"name": "Apress", "earliest_pubdate": datetime.date(2007, 12, 6)},
                    {
                        "name": "Jonno's House of Books",
                        "earliest_pubdate": datetime.date(1970, 1, 1),
                    },
                    {
                        "name": "Morgan Kaufmann",
                        "earliest_pubdate": datetime.date(1991, 10, 15),
                    },
                    {
                        "name": "Prentice Hall",
                        "earliest_pubdate": datetime.date(1995, 1, 15),
                    },
                    {"name": "Sams", "earliest_pubdate": datetime.date(2008, 3, 3)},
                ],
            )

        # Clickhouse will set missing column empty value (0 for number, empty string for text) instead of NULL
        # Missing Date32 column will be set to 1970-01-01.
        # def test_aggregation_default_using_date_from_database(self):
        #     now = timezone.now().astimezone(datetime.timezone.utc)
        #     expr = Min("book__pubdate", default=TruncDate(NowUTC()))
        #     queryset = Publisher.objects.annotate(earliest_pubdate=expr).order_by("name")
        #     self.assertSequenceEqual(
        #         queryset.values("name", "earliest_pubdate"),
        #         [
        #             {"name": "Apress", "earliest_pubdate": datetime.date(2007, 12, 6)},
        #             {"name": "Jonno's House of Books", "earliest_pubdate": now.date()},
        #             {
        #                 "name": "Morgan Kaufmann",
        #                 "earliest_pubdate": datetime.date(1991, 10, 15),
        #             },
        #             {
        #                 "name": "Prentice Hall",
        #                 "earliest_pubdate": datetime.date(1995, 1, 15),
        #             },
        #             {"name": "Sams", "earliest_pubdate": datetime.date(2008, 3, 3)},
        #         ],
        #     )

        def test_aggregation_default_using_datetime_from_python(self):
            expr = Min(
                "store__original_opening",
                filter=~Q(store__name="Amazon.com"),
                # Never take effect
                default=Cast(datetime.datetime(1970, 1, 1), DateTimeField()),
            )
            queryset = Book.objects.annotate(oldest_store_opening=expr).order_by("isbn")
            self.assertSequenceEqual(
                queryset.values("isbn", "oldest_store_opening"),
                [
                    {
                        "isbn": "013235613",
                        "oldest_store_opening": datetime.datetime(
                            1945, 4, 25, 16, 24, 14
                        ),
                    },
                    {
                        "isbn": "013790395",
                        "oldest_store_opening": datetime.datetime(
                            2001, 3, 15, 11, 23, 37
                        ),
                    },
                    {
                        "isbn": "067232959",
                        "oldest_store_opening": datetime.datetime.fromtimestamp(0),
                    },
                    {
                        "isbn": "155860191",
                        "oldest_store_opening": datetime.datetime(
                            1945, 4, 25, 16, 24, 14
                        ),
                    },
                    {
                        "isbn": "159059725",
                        "oldest_store_opening": datetime.datetime(
                            2001, 3, 15, 11, 23, 37
                        ),
                    },
                    {
                        "isbn": "159059996",
                        "oldest_store_opening": datetime.datetime(
                            1945, 4, 25, 16, 24, 14
                        ),
                    },
                ],
            )

        def test_aggregation_default_using_datetime_from_database(self):
            expr = Min(
                "store__original_opening",
                filter=~Q(store__name="Amazon.com"),
                # Never take effect
                default=TruncHour(NowUTC(), output_field=DateTimeField()),
            )
            queryset = Book.objects.annotate(oldest_store_opening=expr).order_by("isbn")
            self.assertSequenceEqual(
                queryset.values("isbn", "oldest_store_opening"),
                [
                    {
                        "isbn": "013235613",
                        "oldest_store_opening": datetime.datetime(
                            1945, 4, 25, 16, 24, 14
                        ),
                    },
                    {
                        "isbn": "013790395",
                        "oldest_store_opening": datetime.datetime(
                            2001, 3, 15, 11, 23, 37
                        ),
                    },
                    {
                        "isbn": "067232959",
                        "oldest_store_opening": datetime.datetime.fromtimestamp(0),
                    },
                    {
                        "isbn": "155860191",
                        "oldest_store_opening": datetime.datetime(
                            1945, 4, 25, 16, 24, 14
                        ),
                    },
                    {
                        "isbn": "159059725",
                        "oldest_store_opening": datetime.datetime(
                            2001, 3, 15, 11, 23, 37
                        ),
                    },
                    {
                        "isbn": "159059996",
                        "oldest_store_opening": datetime.datetime(
                            1945, 4, 25, 16, 24, 14
                        ),
                    },
                ],
            )

        def test_aggregation_default_using_decimal_from_python(self):
            result = Book.objects.filter(rating__lt=3.0).aggregate(
                value=Sum("price", default=Decimal("0.00")),
            )
            self.assertEqual(result["value"], Decimal("0.00"))

        # Clickhouse will set missing column empty value (0 for number, empty string for text) instead of NULL
        # def test_aggregation_default_using_decimal_from_database(self):
        #     result = Book.objects.filter(rating__lt=3.0).aggregate(
        #         value=Sum("price", default=Pi()),
        #     )
        #     self.assertAlmostEqual(result["value"], Decimal.from_float(math.pi), places=6)

        # DB::Exception: There is no supertype for types Decimal(38, 2), Float64
        # because some of them have no lossless conversion to Decimal:
        # While processing coalesce(sum(CAST(if(rating < 3., price, NULL), 'Nullable(Decimal(6, 2))')), avg(pages) / 10.).
        # def test_aggregation_default_passed_another_aggregate(self):
        #     result = Book.objects.aggregate(
        #         value=Sum("price", filter=Q(rating__lt=3.0), default=Avg("pages") / 10.0),
        #     )
        #     self.assertAlmostEqual(result["value"], Decimal("61.72"), places=2)

        def test_aggregation_default_after_annotation(self):
            result = Publisher.objects.annotate(
                double_num_awards=F("num_awards") * 2,
            ).aggregate(value=Sum("double_num_awards", default=0))
            self.assertEqual(result["value"], 40)

        def test_aggregation_default_not_in_aggregate(self):
            result = Publisher.objects.annotate(
                avg_rating=Avg("book__rating", default=2.5),
            ).aggregate(Sum("num_awards"))
            self.assertEqual(result["num_awards__sum"], 20)

        def test_exists_none_with_aggregate(self):
            qs = Book.objects.annotate(
                count=Count("id"),
                exists=Exists(Author.objects.none()),
            )
            self.assertEqual(len(qs), 6)

    if compat.dj_ge4:

        def test_exists_extra_where_with_aggregate(self):
            qs = Book.objects.annotate(
                count=Count("id"),
                exists=Exists(Author.objects.extra(where=["1=0"])),
            )
            self.assertEqual(len(qs), 6)
