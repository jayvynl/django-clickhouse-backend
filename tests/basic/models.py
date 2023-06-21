"""
Bare-bones model

This is a basic model with only two non-primary-key fields.
"""
import uuid

from django.db import models

from clickhouse_backend.models import ClickhouseModel


class Article(ClickhouseModel):
    headline = models.CharField(max_length=100, default="Default headline")
    pub_date = models.DateTimeField()

    class Meta:
        ordering = ("pub_date", "headline")

    def __str__(self):
        return self.headline


class FeaturedArticle(ClickhouseModel):
    article = models.OneToOneField(Article, models.CASCADE, related_name="featured")


class ArticleSelectOnSave(Article):
    class Meta:
        proxy = True
        select_on_save = True


class SelfRef(ClickhouseModel):
    selfref = models.ForeignKey(
        "self",
        models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    article = models.ForeignKey(Article, models.SET_NULL, null=True, blank=True)

    def __str__(self):
        # This method intentionally doesn't work for all cases - part
        # of the test for ticket #20278
        return SelfRef.objects.get(selfref=self).pk


class PrimaryKeyWithDefault(ClickhouseModel):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4)


class ChildPrimaryKeyWithDefault(PrimaryKeyWithDefault):
    pass


class DjangoArticle(models.Model):
    headline = models.CharField(max_length=100, default="Default headline")
    pub_date = models.DateTimeField()

    class Meta:
        ordering = ("pub_date", "headline")

    def __str__(self):
        return self.headline
