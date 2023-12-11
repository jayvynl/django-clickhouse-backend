from django.db import models


class WatchSeries(models.Model):
    date_id = models.DateField()
    uid = models.CharField(max_length=100)
    show = models.CharField(max_length=255)
    episode = models.CharField(max_length=255)
