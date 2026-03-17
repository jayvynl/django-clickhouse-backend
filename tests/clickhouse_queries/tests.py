from django.db import NotSupportedError, connection
from django.db.models import Count, Window
from django.db.models.functions import Rank
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from . import models


class DeleteWithAnnotationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a1, cls.a2 = models.Author.objects.bulk_create(
            [models.Author(name="a1", num=1), models.Author(name="a2", num=2)]
        )
        models.Book.objects.bulk_create(
            [
                models.Book(name="b1", author=cls.a1),
                models.Book(name="b2", author=cls.a1),
                models.Book(name="b3", author=cls.a2),
            ]
        )

    def test_delete_with_annotation_filter(self):
        """DELETE with annotation-based filter should not generate positional GROUP BY."""
        # a1 has 2 books, a2 has 1. Delete authors with more than 1 book.
        models.Author.objects.annotate(book_count=Count("books")).filter(
            book_count__gt=1
        ).delete()
        self.assertEqual(models.Author.objects.count(), 1)
        self.assertEqual(models.Author.objects.get().name, "a2")


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
        b1, b2 = (
            models.Book.objects.filter(author__name=self.a1.name)
            .prewhere(author_id=self.a1.id)
            .order_by("id")
        )
        self.assertTrue(b1.id == self.b1.id and b2.id == self.b2.id)

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
            NotSupportedError,
            "Window function is disallowed in the prewhere clause.",
        ):
            list(
                models.Book.objects.annotate(
                    rank=Window(Rank(), partition_by="author", order_by="name")
                ).prewhere(rank__gt=1)
            )


class SettingsInsertTests(TestCase):
    def test_bulk_create_with_settings_succeeds(self):
        models.Author.objects.settings(max_insert_threads=4).bulk_create(
            [
                models.Author(name="s1", num=1),
                models.Author(name="s2", num=2),
            ]
        )
        self.assertEqual(models.Author.objects.filter(name__in=["s1", "s2"]).count(), 2)

    def test_bulk_create_with_settings_generates_settings_sql(self):
        with CaptureQueriesContext(connection) as ctx:
            models.Author.objects.settings(max_insert_threads=4).bulk_create(
                [
                    models.Author(name="s3", num=3),
                ]
            )
        insert_sqls = [q["sql"] for q in ctx.captured_queries if "INSERT" in q["sql"]]
        self.assertTrue(insert_sqls, "No INSERT query captured")
        sql = insert_sqls[0]
        self.assertIn("SETTINGS", sql)
        self.assertIn("max_insert_threads", sql)

    def test_bulk_create_without_settings_omits_settings_sql(self):
        with CaptureQueriesContext(connection) as ctx:
            models.Author.objects.bulk_create(
                [
                    models.Author(name="s4", num=4),
                ]
            )
        insert_sqls = [q["sql"] for q in ctx.captured_queries if "INSERT" in q["sql"]]
        self.assertTrue(insert_sqls, "No INSERT query captured")
        self.assertNotIn("SETTINGS", insert_sqls[0])
