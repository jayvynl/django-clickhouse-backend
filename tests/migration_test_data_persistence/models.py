from django.db import models

from clickhouse_backend.models import ClickhouseModel


class Book(ClickhouseModel):
    title = models.CharField(max_length=100)


class Unmanaged(ClickhouseModel):
    title = models.CharField(max_length=100)

    class Meta:
        managed = False
