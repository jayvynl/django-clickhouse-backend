from django.db import models


class Func(models.Func):
    @property
    def function(self):
        return self.__class__.__name__
