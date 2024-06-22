from django.db.models import CASCADE, ForeignKey

from clickhouse_backend import models


class Classification(models.ClickhouseModel):
    code = models.FixedStringField(max_bytes=10)


class Employee(models.ClickhouseModel):
    name = models.FixedStringField(max_bytes=40, blank=False, null=False)
    salary = models.UInt32Field()
    department = models.FixedStringField(max_bytes=40, blank=False, null=False)
    hire_date = models.DateField(blank=False, null=False)
    age = models.Int32Field(blank=False, null=False)
    classification = ForeignKey("Classification", on_delete=CASCADE, null=True)
    bonus = models.DecimalField(decimal_places=2, max_digits=15, null=True)


class Detail(models.ClickhouseModel):
    value = models.JSONField()

    class Meta:
        required_db_features = {"supports_json_field"}
