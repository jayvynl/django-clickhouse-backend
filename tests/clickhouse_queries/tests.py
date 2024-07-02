from django.db import NotSupportedError
from django.db.models import Count, Window
from django.db.models.functions import Rank
from django.test import TestCase

from . import models


class QueriesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a1, cls.a2 = models.Author.objects.bulk_create(
            [models.Author(name="a1", num=1001), models.Author(name="a2", num=2002)]
        )
        cls.b1, cls.b2, cls.b3, cls.b4 = models.Book.objects.bulk_create(
            [
                models.Book(name="b1", author=cls.a1),
                models.Book(name="b2", author=cls.a1),
                models.Book(name="b3", author=cls.a2),
                models.Book(name="b4", author=cls.a2),
            ]
        )
        models.Article.objects.bulk_create(
            [
                models.Article(title="t1", book=cls.b1.id),
                models.Article(title="t2", book=cls.b2.id),
            ]
        )

    def test_prewhere(self):
        qs = models.Author.objects.prewhere(name="a1")
        self.assertIn("PREWHERE", str(qs.query))
        self.assertEqual(qs[0].name, "a1")

    def test_prewhere_fk(self):
        self.assertQuerySetEqual(
            models.Book.objects.filter(author__name=self.a1.name)
            .prewhere(author_id=self.a1.id)
            .order_by("name"),
            [self.b1, self.b2],
        )

    # clickhouse backend will generate suitable query, but clickhouse will raise exception.
    # clickhouse 23.11
    # DB::Exception: Missing columns: 'clickhouse_queries_article.book' while processing query: 'SELECT name FROM clickhouse_queries_book AS U0 PREWHERE id = clickhouse_queries_article.book', required columns: 'name' 'id' 'clickhouse_queries_article.book', maybe you meant: 'name' or 'id': While processing (SELECT U0.name FROM clickhouse_queries_book AS U0 PREWHERE U0.id = clickhouse_queries_article.book) AS book_name.
    # clickhouse 24.6
    # DB::Exception: Resolve identifier 'clickhouse_queries_article.book' from parent scope only supported for constants and CTE. Actual test_default.clickhouse_queries_article.book node type COLUMN. In scope (SELECT U0.name FROM clickhouse_queries_book AS U0 PREWHERE U0.id = clickhouse_queries_article.book) AS book_name.
    # def test_prewhere_subquery(self):
    #     a = models.Article.objects.annotate(
    #         book_name=Subquery(
    #             models.Book.objects.prewhere(id=OuterRef("book")).values("name")
    #         )
    #     ).get(title="t1")
    #     self.assertEqual(a.book_name, self.b1.name)

    def test_prewhere_agg(self):
        with self.assertRaisesMessage(
            NotSupportedError,
            "Aggregate function is disallowed in the prewhere clause.",
        ):
            list(
                models.Author.objects.annotate(count=Count("books")).prewhere(
                    count__gt=0
                )
            )

    def test_prewhere_window(self):
        with self.assertRaisesMessage(
            NotSupportedError, "Window function is disallowed in the prewhere clause."
        ):
            list(
                models.Book.objects.annotate(
                    rank=Window(Rank(), partition_by="author", order_by="name")
                ).prewhere(rank__gt=1)
            )
