from django.test import TestCase

from . import models


class QueriesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a1 = models.Author.objects.create(name="a1", num=1001)

    def test_update(self):
        with self.settings(CLICKHOUSE_ENABLE_UPDATE_ROWCOUNT=True):
            self.assertEqual(models.Author.objects.update(name="a11"), 1)
            with self.assertNumQueries(1):
                self.a1.save()
            self.a1.refresh_from_db()
        with self.settings(CLICKHOUSE_ENABLE_UPDATE_ROWCOUNT=False):
            self.assertEqual(models.Author.objects.update(name="a11"), -1)
            with self.assertNumQueries(2):
                self.a1.save()
            with self.assertRaises(models.Author.MultipleObjectsReturned):
                self.a1.refresh_from_db()

    # regression test for https://github.com/jayvynl/django-clickhouse-backend/issues/99
    def test_update_special_string_val(self):
        self.a1.name = "where **"
        self.a1.save()
        self.a1.refresh_from_db()
        self.assertEqual(self.a1.name, "where **")
