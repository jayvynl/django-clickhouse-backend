from django.db import models

from clickhouse_backend.models import ClickhouseModel


class Author(ClickhouseModel):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=255)
    slug = models.SlugField(null=True)
    age = models.IntegerField(default=0)
    silly_field = models.BooleanField(default=False)


class Tribble(ClickhouseModel):
    id = models.BigAutoField(primary_key=True)
    fluffy = models.BooleanField(default=True)
