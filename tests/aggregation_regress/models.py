from django.db import models

from clickhouse_backend.models import ClickhouseModel


class Author(ClickhouseModel):
    name = models.CharField(max_length=100)
    age = models.IntegerField()
    friends = models.ManyToManyField("self", blank=True)


class Publisher(ClickhouseModel):
    name = models.CharField(max_length=255)
    num_awards = models.IntegerField()


class Book(ClickhouseModel):
    isbn = models.CharField(max_length=9)
    name = models.CharField(max_length=255)
    pages = models.IntegerField()
    rating = models.FloatField()
    price = models.DecimalField(decimal_places=2, max_digits=6)
    authors = models.ManyToManyField(Author)
    contact = models.ForeignKey(Author, models.CASCADE, related_name="book_contact_set")
    publisher = models.ForeignKey(Publisher, models.CASCADE)
    pubdate = models.DateField()

    class Meta:
        ordering = ("name",)


class Store(ClickhouseModel):
    name = models.CharField(max_length=255)
    books = models.ManyToManyField(Book)
    original_opening = models.DateTimeField()


class HardbackBook(Book):
    weight = models.FloatField()


# Models for ticket #21150
class Alfa(ClickhouseModel):
    name = models.CharField(max_length=10, null=True)


class Bravo(ClickhouseModel):
    pass


class Charlie(ClickhouseModel):
    alfa = models.ForeignKey(Alfa, models.SET_NULL, null=True)
    bravo = models.ForeignKey(Bravo, models.SET_NULL, null=True)


class SelfRefFK(ClickhouseModel):
    name = models.CharField(max_length=50)
    parent = models.ForeignKey(
        "self", models.SET_NULL, null=True, blank=True, related_name="children"
    )
