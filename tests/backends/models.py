from django.db import models

from clickhouse_backend.models import ClickhouseModel


class Square(ClickhouseModel):
    root = models.IntegerField()
    square = models.PositiveIntegerField()

    def __str__(self):
        return "%s ** 2 == %s" % (self.root, self.square)


class Person(ClickhouseModel):
    first_name = models.CharField(max_length=20)
    last_name = models.CharField(max_length=20)

    def __str__(self):
        return "%s %s" % (self.first_name, self.last_name)


class SchoolClassManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().exclude(year=1000)


class SchoolClass(ClickhouseModel):
    year = models.PositiveIntegerField()
    day = models.CharField(max_length=9, blank=True)
    last_updated = models.DateTimeField()

    objects = SchoolClassManager()


class VeryLongModelNameZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ(ClickhouseModel):
    primary_key_is_quite_long_zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz = (
        models.BigAutoField(primary_key=True)
    )
    charfield_is_quite_long_zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz = models.CharField(
        max_length=100
    )
    m2m_also_quite_long_zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz = (
        models.ManyToManyField(Person, blank=True)
    )


class Tag(ClickhouseModel):
    name = models.CharField(max_length=30)


class Reporter(ClickhouseModel):
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)

    def __str__(self):
        return "%s %s" % (self.first_name, self.last_name)


class ReporterProxy(Reporter):
    class Meta:
        proxy = True


class Article(ClickhouseModel):
    headline = models.CharField(max_length=100)
    pub_date = models.DateField()
    reporter = models.ForeignKey(Reporter, models.CASCADE)
    reporter_proxy = models.ForeignKey(
        ReporterProxy,
        models.SET_NULL,
        null=True,
        related_name="reporter_proxy",
    )

    def __str__(self):
        return self.headline


class Item(ClickhouseModel):
    name = models.CharField(max_length=30)
    date = models.DateField()
    time = models.TimeField()
    last_modified = models.DateTimeField()

    def __str__(self):
        return self.name


class Object(ClickhouseModel):
    related_objects = models.ManyToManyField(
        "self", db_constraint=False, symmetrical=False
    )
    obj_ref = models.ForeignKey("ObjectReference", models.CASCADE, null=True)

    def __str__(self):
        return str(self.id)


class ObjectReference(ClickhouseModel):
    obj = models.ForeignKey(Object, models.CASCADE, db_constraint=False)

    def __str__(self):
        return str(self.obj_id)


class ObjectSelfReference(ClickhouseModel):
    key = models.CharField(max_length=3, unique=True)
    obj = models.ForeignKey("ObjectSelfReference", models.SET_NULL, null=True)


class CircularA(ClickhouseModel):
    key = models.CharField(max_length=3, unique=True)
    obj = models.ForeignKey("CircularB", models.SET_NULL, null=True)

    def natural_key(self):
        return (self.key,)


class CircularB(ClickhouseModel):
    key = models.CharField(max_length=3, unique=True)
    obj = models.ForeignKey("CircularA", models.SET_NULL, null=True)

    def natural_key(self):
        return (self.key,)


class RawData(ClickhouseModel):
    raw_data = models.BinaryField()


class Author(ClickhouseModel):
    name = models.CharField(max_length=255, unique=True)


class Book(ClickhouseModel):
    author = models.ForeignKey(Author, models.CASCADE, to_field="name")


class SQLKeywordsModel(ClickhouseModel):
    id = models.BigAutoField(primary_key=True, db_column="select")
    reporter = models.ForeignKey(Reporter, models.CASCADE, db_column="where")

    class Meta:
        db_table = "order"
