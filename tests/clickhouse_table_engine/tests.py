from django.db import connection
from django.test import TestCase

from .models import EngineWithSettings


class TestEngineSettings(TestCase):
    def test(self):
        opts = EngineWithSettings._meta
        with connection.cursor() as cursor:
            cursor.execute(
                f"select engine_full from system.tables where table='{opts.db_table}'"
            )
            engine_full = cursor.fetchone()[0]
        for k, v in opts.engine.settings.items():
            assert f"{k} = {v}" in engine_full
