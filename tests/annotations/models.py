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


class Store(ClickhouseModel):
    name = models.CharField(max_length=255)
    books = models.ManyToManyField(Book)
    original_opening = models.DateTimeField()
    area = models.IntegerField(null=True, db_column="surface")


class DepartmentStore(Store):
    chain = models.CharField(max_length=255)


class Employee(ClickhouseModel):
    # The order of these fields matter, do not change. Certain backends
    # rely on field ordering to perform database conversions, and this
    # model helps to test that.
    first_name = models.CharField(max_length=20)
    manager = models.BooleanField(default=False)
    last_name = models.CharField(max_length=20)
    store = models.ForeignKey(Store, models.CASCADE)
    age = models.IntegerField()
    salary = models.DecimalField(max_digits=8, decimal_places=2)


class Company(ClickhouseModel):
    name = models.CharField(max_length=200)
    motto = models.CharField(max_length=200, null=True, blank=True)
    ticker_name = models.CharField(max_length=10, null=True, blank=True)
    description = models.CharField(max_length=200, null=True, blank=True)


class Ticket(ClickhouseModel):
    active_at = models.DateTimeField()
