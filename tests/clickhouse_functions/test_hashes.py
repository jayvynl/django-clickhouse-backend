from django.test import TestCase

from clickhouse_backend import models

from .models import Author


class HashTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.john = Author.objects.create(name="John Smith")

    def test(self):
        for func in [
            models.halfMD5,
            models.sipHash64,
            models.sipHash128,
            models.sipHash128Reference,
            models.cityHash64,
            models.farmHash64,
            models.farmFingerprint64,
        ]:
            Author.objects.annotate(
                v=func("name", "alias", "goes_by", "birthday", "age")
            )

        for func in [
            models.sipHash64Keyed,
            models.sipHash128Keyed,
            models.sipHash128ReferenceKeyed,
        ]:
            Author.objects.annotate(
                v=func("age", "age", "name", "alias", "goes_by", "birthday", "age")
            )

        for func in [
            models.MD4,
            models.MD5,
            models.SHA1,
            models.SHA224,
            models.SHA256,
            models.SHA512,
            models.BLAKE3,
            models.URLHash,
        ]:
            Author.objects.annotate(v=func("name"))

        for func in [
            models.intHash32,
            models.intHash64,
        ]:
            Author.objects.annotate(v=func("age"))

        Author.objects.annotate(v=models.URLHash("name", 2))
