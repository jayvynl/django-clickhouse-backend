from django.db import models

from clickhouse_backend.models import ClickhouseModel


class Author(ClickhouseModel):
    name = models.CharField(max_length=100)
    age = models.IntegerField()
    friends = models.ManyToManyField("self", blank=True)
    rating = models.FloatField(null=True)

    def __str__(self):
        return self.name


class Publisher(ClickhouseModel):
    name = models.CharField(max_length=255)
    num_awards = models.IntegerField()

    def __str__(self):
        return self.name


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

    def __str__(self):
        return self.name


class Store(ClickhouseModel):
    name = models.CharField(max_length=255)
    books = models.ManyToManyField(Book)
    original_opening = models.DateTimeField()

    def __str__(self):
        return self.name
