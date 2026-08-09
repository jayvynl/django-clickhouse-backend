import json as jsonlib
import utils
from decimal import Decimal
from functools import partial
from unittest import skipUnless

from django.core.serializers.json import DjangoJSONEncoder
from django.db import DatabaseError, NotSupportedError, connection
from django.db.models import Count, F, IntegerField, Value
from django.db.models.fields.json import KeyTextTransform, KeyTransform
from django.db.models.functions import Cast
from django.test import TestCase
from django.test.utils import isolate_apps

from clickhouse_backend import compat, models


HINTS = {
    "max_dynamic_types": 4,
    "max_dynamic_paths": 8,
    "typed_paths": {"a.b": "UInt32"},
    "skip_paths": ["a.c"],
    "skip_regexps": ["tmp[0-9]"],
}


json_model = partial(utils.json_model, "clickhouse_fields")


class JsonFieldTests(TestCase):
    def test_deconstruct(self):
        field = models.JSONField(name="field")
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "clickhouse_backend.models.JSONField")

    def test_db_type(self):
        self.assertEqual(
            models.JSONField(name="field").db_type(connection),
            "JSON",
        )
        self.assertEqual(
            models.JSONField(name="field", null=True).db_type(connection),
            "Nullable(JSON)",
        )

    def test_db_type_hints(self):
        self.assertEqual(
            models.JSONField(name="field", **HINTS).db_type(connection),
            "JSON(max_dynamic_types=4, max_dynamic_paths=8, `a.b` UInt32, "
            "SKIP `a.c`, SKIP REGEXP 'tmp[0-9]')",
        )
        self.assertEqual(
            models.JSONField(name="field", null=True, max_dynamic_paths=8).db_type(
                connection
            ),
            "Nullable(JSON(max_dynamic_paths=8))",
        )

    def test_deconstruct_hints(self):
        field = models.JSONField(name="field", **HINTS)
        self.assertEqual(field.deconstruct()[3], HINTS)

    def test_hints(self):
        with json_model(**HINTS) as JSONModel:
            table = JSONModel._meta.db_table
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT type FROM system.columns "
                    "WHERE database = currentDatabase() AND table = %s AND name = %s",
                    [table, "json"],
                )
                # Hints are rendered the way clickhouse renders them back.
                self.assertEqual(
                    cursor.fetchone()[0],
                    JSONModel._meta.get_field("json").db_type(connection),
                )
                # A hint only applies to a value clickhouse parses itself, so the
                # value is inserted as JSON text instead of natively.
                cursor.execute(
                    'INSERT INTO "%s" (json) VALUES (%%s)' % table,
                    ['{"a": {"b": "7", "c": 2}, "tmp1": 5, "tmp": 6}'],
                )
            # A typed path converts its value, a skipped one is dropped, and a
            # SKIP REGEXP has to match a whole path.
            self.assertEqual(
                JSONModel.objects.values_list("json", flat=True)[0],
                {"a": {"b": 7}, "tmp": 6},
            )
            self.assertEqual(JSONModel.objects.filter(json__a__b=7).count(), 1)

    def test_typed_paths_check(self):
        with isolate_apps("clickhouse_fields"):

            class Managed(models.ClickhouseModel):
                json = models.JSONField(typed_paths={"a": "UInt32"})

            class Unmanaged(models.ClickhouseModel):
                json = models.JSONField(typed_paths={"a": "UInt32"})

                class Meta:
                    managed = False

            (warning,) = Managed._meta.get_field("json").check()
            self.assertEqual(
                warning.msg,
                "clickhouse-driver cannot insert into a JSON column which has a "
                "typed path.",
            )
            self.assertEqual(Unmanaged._meta.get_field("json").check(), [])

    def test_escaping(self):
        # A value travels as JSON text, natively for an insert and escaped into
        # SQL for a comparison.
        with json_model() as JSONModel:
            for value in [
                {"a": "b\\c"},
                {"a": "c\\"},
                {"a": "it's"},
                {"a": 'say "hi"'},
                {"a": "line\nbreak"},
                {"a": "100% %s"},
                {"a": "x\x00y"},
                {"a": "中文"},
                {"a\\b": "`x`"},
                # A key travels inside the query, where a literal % breaks the
                # interpolation of its params.
                {"100%": "x"},
                {"a%b": {"c": 1}},
            ]:
                with self.subTest(value=value):
                    o = JSONModel.objects.create(json=value)
                    self.assertEqual(JSONModel.objects.get(id=o.id).json, value)
                    self.assertTrue(JSONModel.objects.filter(json=value).exists())
                    key, key_value = next(iter(value.items()))
                    self.assertTrue(
                        JSONModel.objects.filter(
                            **{"json__%s" % key: key_value}
                        ).exists()
                    )

    def test_raw_query(self):
        with json_model() as JSONModel:
            JSONModel.objects.create(json={"a": 1})
            # A raw query has no select_format, so the value arrives as the dict
            # clickhouse-driver decoded natively instead of as JSON text.
            (o,) = JSONModel.objects.raw(
                'SELECT id, json FROM "%s"' % JSONModel._meta.db_table
            )
            self.assertEqual(o.json, {"a": 1})

    def test_encoder_decoder(self):
        class Decoder(jsonlib.JSONDecoder):
            def __init__(self, **kwargs):
                kwargs["object_hook"] = lambda obj: {**obj, "decoded": True}
                super().__init__(**kwargs)

        with json_model(encoder=DjangoJSONEncoder, decoder=Decoder) as JSONModel:
            o = JSONModel.objects.create(json={"a": Decimal("1.5")})
            self.assertEqual(
                JSONModel.objects.get(id=o.id).json, {"a": "1.5", "decoded": True}
            )

    def test_null(self):
        with json_model(null=True) as JSONModel:
            o = JSONModel.objects.create(json=None)
            self.assertIsNone(JSONModel.objects.get(id=o.id).json)
            self.assertEqual(JSONModel.objects.filter(json__isnull=True).count(), 1)

    def test_null_is_stored_as_empty_object(self):
        with json_model() as JSONModel:
            # Clickhouse takes a root null instead of rejecting it like every
            # other value which is not an object, and stores an empty object.
            o = JSONModel.objects.create(json=None)
            self.assertEqual(JSONModel.objects.get(id=o.id).json, {})

            # A key whose value is null is not stored either, it is
            # indistinguishable from a key which is absent.
            o = JSONModel.objects.create(json={"a": None, "b": 1})
            self.assertEqual(JSONModel.objects.get(id=o.id).json, {"b": 1})

    def test_query(self):
        with json_model() as JSONModel:
            v = {"a": [1, 2, 3], "b": [{"c": 1}, {"c": 2}], "c": {"d": "e"}}
            o = JSONModel.objects.create(json=v)
            o.refresh_from_db()
            self.assertEqual(o.json, v)

            (o2,) = JSONModel.objects.bulk_create([JSONModel(json={"a": 9})])
            self.assertEqual(JSONModel.objects.get(id=o2.id).json, {"a": 9})

            # Keys of an object are stored sorted.
            self.assertEqual(
                JSONModel.objects.filter(id=o.id).values_list("json", flat=True)[0],
                {"a": [1, 2, 3], "b": [{"c": 1}, {"c": 2}], "c": {"d": "e"}},
            )

    def test_field_lookups(self):
        with json_model() as JSONModel:
            JSONModel.objects.create(json={"a": 1})
            # Lookups django compiles itself, against the column read as text.
            self.assertEqual(JSONModel.objects.filter(json__icontains="a").count(), 1)
            self.assertEqual(JSONModel.objects.filter(json__regex="1").count(), 1)
            self.assertEqual(JSONModel.objects.filter(json__iregex="1").count(), 1)
            self.assertEqual(JSONModel.objects.filter(json__startswith="1").count(), 0)
            self.assertEqual(JSONModel.objects.filter(json__isnull=True).count(), 0)
            # Comparing the column itself with a number is a clickhouse error,
            # only a key path has a definite type to convert to.
            with self.assertRaises(DatabaseError):
                JSONModel.objects.filter(json__gt=0).count()

    def test_has_key(self):
        with json_model() as JSONModel:
            JSONModel.objects.create(
                json={
                    "a": 1,
                    "c": {"d": 2},
                    "e": [1, 2],
                    "n": None,
                    "0": 3,
                    "f": [{"g": 1}],
                }
            )
            JSONModel.objects.create(json={"z": 9})

            for lookup, value, count in [
                ("has_key", "a", 1),  # a scalar
                ("has_key", "c", 1),  # a nested object
                ("has_key", "e", 1),  # an array
                ("has_key", "0", 1),  # a digit, which is a key at the root
                ("has_key", "zz", 0),
                # A key whose value is null does not exist, clickhouse drops it.
                ("has_key", "n", 0),
                ("has_keys", ["a", "c"], 1),
                ("has_keys", ["a", "zz"], 0),
                ("has_any_keys", ["a", "zz"], 1),
                ("has_any_keys", ["yy", "zz"], 0),
            ]:
                with self.subTest(lookup=lookup, value=value):
                    self.assertEqual(
                        JSONModel.objects.filter(
                            **{"json__%s" % lookup: value}
                        ).count(),
                        count,
                    )
            # On a key path rather than the field itself.
            self.assertEqual(JSONModel.objects.filter(json__c__has_key="d").count(), 1)
            self.assertEqual(JSONModel.objects.filter(json__c__has_key="z").count(), 0)
            self.assertEqual(JSONModel.objects.filter(json__zz__has_key="d").count(), 0)
            # A path ending at an array index has no sub-object accessor, and one
            # which follows an index is tested through the JSON text before it.
            self.assertEqual(JSONModel.objects.filter(json__e__has_key="0").count(), 1)
            self.assertEqual(JSONModel.objects.filter(json__e__has_key="9").count(), 0)
            self.assertEqual(
                JSONModel.objects.filter(json__f__0__has_key="g").count(), 1
            )
            self.assertEqual(
                JSONModel.objects.filter(json__f__0__has_key="z").count(), 0
            )
            # A key transform as the key names a path relative to the lhs.
            self.assertEqual(
                JSONModel.objects.filter(
                    json__has_key=KeyTransform("d", KeyTransform("c", "json"))
                ).count(),
                1,
            )

    def test_contains(self):
        with json_model() as JSONModel:
            v = {"a": [1, 2, 3], "b": {"c": 1, "d": 2}, "e": [{"f": 1, "g": 2}]}
            JSONModel.objects.create(json=v)
            JSONModel.objects.create(json={"a": 9})

            for value, count in [
                (v, 1),
                ({}, 2),  # Every value is an object.
                ({"b": {"c": 1}}, 1),  # A nested object is contained.
                ({"b": {"c": 1, "z": 1}}, 0),
                ({"b": {"c": 2}}, 0),
                ({"a": [3, 1]}, 1),  # An array holds the elements in any order.
                ({"a": [1, 4]}, 0),
                ({"a": []}, 1),
                ({"a": {}}, 0),  # An array is not an object.
                ({"e": [{"f": 1}]}, 1),  # An object inside an array.
                ({"e": [{"f": 2}]}, 0),
                ({"a": 1}, 0),  # Only the top level looks inside an array.
                ({"z": 1}, 0),
            ]:
                with self.subTest(value=value):
                    self.assertEqual(
                        JSONModel.objects.filter(json__contains=value).count(), count
                    )
                    self.assertEqual(
                        JSONModel.objects.exclude(json__contains=value).count(),
                        2 - count,
                    )

            # On a key path, where postgres makes its one exception: an array
            # contains a primitive value of its own.
            for lookup, value, count in [
                ("json__a__contains", 2, 1),
                ("json__a__contains", 9, 1),  # The value itself, not an array.
                ("json__a__contains", 4, 0),
                ("json__a__contains", [2, 3], 1),
                ("json__b__contains", {"c": 1}, 1),
                ("json__e__contains", [{"f": 1}], 1),
                ("json__e__contains", {"f": 1}, 0),
                ("json__b__c__contains", 1, 1),
                ("json__z__contains", 1, 0),
            ]:
                with self.subTest(lookup=lookup, value=value):
                    self.assertEqual(
                        JSONModel.objects.filter(**{lookup: value}).count(), count
                    )

            with self.assertRaisesMessage(
                NotSupportedError,
                "contains lookup only supports a literal value on this database backend.",
            ):
                JSONModel.objects.filter(json__contains=F("json")).count()

    def test_contained_by(self):
        with json_model() as JSONModel:
            v = {"a": [1, 2], "b": {"c": 1}}
            JSONModel.objects.create(json=v)
            JSONModel.objects.create(json={})

            for value, count in [
                (v, 2),
                ({}, 1),  # Only an empty object is contained by an empty one.
                ({"a": [1, 2, 3], "b": {"c": 1, "d": 2}, "z": 9}, 2),
                ({"a": [1, 2, 3], "b": {"c": 2}}, 1),
                ({"a": [1], "b": {"c": 1}}, 1),
                ({"a": 1, "b": {"c": 1}}, 1),
            ]:
                with self.subTest(value=value):
                    self.assertEqual(
                        JSONModel.objects.filter(json__contained_by=value).count(),
                        count,
                    )
                    self.assertEqual(
                        JSONModel.objects.exclude(json__contained_by=value).count(),
                        2 - count,
                    )

            for lookup, value, count in [
                ("json__a__contained_by", [1, 2, 3], 1),
                ("json__a__contained_by", [1, 3], 0),
                ("json__b__contained_by", {"c": 1, "d": 2}, 1),
                ("json__b__contained_by", {"d": 2}, 0),
                ("json__b__c__contained_by", [1, 2], 1),  # A primitive of an array.
                ("json__b__c__contained_by", 1, 1),
                ("json__z__contained_by", {"a": 1}, 0),
            ]:
                with self.subTest(lookup=lookup, value=value):
                    self.assertEqual(
                        JSONModel.objects.filter(**{lookup: value}).count(), count
                    )

            with self.assertRaisesMessage(
                NotSupportedError,
                "contained_by lookup only supports a literal value on this database backend.",
            ):
                JSONModel.objects.filter(json__contained_by=F("json")).count()

    def test_value_expression(self):
        with json_model() as JSONModel:
            JSONModel.objects.create(json={"a": 1})
            # A value is prepared as JSON text, which JSONField.get_placeholder
            # casts back to JSON wherever it is compared or read as one.
            value = Value({"a": 1}, models.JSONField())
            self.assertTrue(JSONModel.objects.filter(json=value).exists())
            self.assertEqual(
                JSONModel.objects.annotate(x=value).values("x")[0], {"x": {"a": 1}}
            )

    @skipUnless(compat.dj_ge5, "db_default requires django 5.0.")
    def test_db_default(self):
        with json_model(db_default={"a": 1}) as JSONModel:
            o = JSONModel.objects.create()
            self.assertEqual(JSONModel.objects.get(id=o.id).json, {"a": 1})

            # A row taking the default and one giving a value travel in the same
            # insert, which renders the values as SQL instead of sending them
            # natively, because the default is not a placeholder of its own.
            JSONModel.objects.bulk_create([JSONModel(json={"b": 2}), JSONModel()])
            self.assertCountEqual(
                JSONModel.objects.values_list("json", flat=True),
                [{"a": 1}, {"b": 2}, {"a": 1}],
            )

    def test_update(self):
        with json_model() as JSONModel:
            o = JSONModel.objects.create(json={"a": 9})

            # A heterogeneous array is stored as an Array(Dynamic) by UPDATE,
            # which is only readable as text.
            JSONModel.objects.filter(id=o.id).update(json={"a": [1, {"b": 2}]})
            self.assertEqual(JSONModel.objects.get(id=o.id).json, {"a": [1, {"b": 2}]})

            o.json = {"a": "9"}
            o.save()
            self.assertEqual(JSONModel.objects.get(id=o.id).json, {"a": "9"})

    def test_key_transform(self):
        with json_model() as JSONModel:
            v = {"a": [1, 2, 3], "b": [{"c": 1}, {"c": 2}], "c": {"d": "e"}, "0": 7}
            o = JSONModel.objects.create(json=v)
            qs = JSONModel.objects.filter(id=o.id)

            self.assertEqual(qs.values("json__a")[0], {"json__a": [1, 2, 3]})
            # The root of a JSON column is an object, a digit is a key there.
            self.assertEqual(qs.values("json__0")[0], {"json__0": 7})
            self.assertEqual(qs.values("json__b__0__c")[0], {"json__b__0__c": 1})
            self.assertEqual(qs.values("json__c__d")[0], {"json__c__d": "e"})
            self.assertEqual(qs.values("json__c")[0], {"json__c": {"d": "e"}})
            # A path ending at an array index has no sub-object accessor.
            self.assertEqual(qs.values("json__a__0")[0], {"json__a__0": 1})
            # A negative index counts from the end, as it does on postgres.
            self.assertEqual(qs.values("json__a__-1")[0], {"json__a__-1": 3})
            self.assertEqual(qs.values("json__b__-1__c")[0], {"json__b__-1__c": 2})
            self.assertEqual(qs.values("json__a__-9")[0], {"json__a__-9": None})
            # A text transform of a key which follows an array index.
            self.assertEqual(
                qs.annotate(
                    x=KeyTextTransform(
                        "c", KeyTransform("0", KeyTransform("b", "json"))
                    )
                ).values("x")[0],
                {"x": "1"},
            )
            # A key which is absent is NULL, as it is on other backends.
            self.assertEqual(qs.values("json__z")[0], {"json__z": None})

            self.assertEqual(
                qs.annotate(x=F("json__c")).values("x")[0], {"x": {"d": "e"}}
            )
            self.assertEqual(
                qs.annotate(x=KeyTextTransform("d", KeyTransform("c", "json"))).values(
                    "x"
                )[0],
                {"x": "e"},
            )
            self.assertEqual(
                qs.annotate(
                    x=Cast(KeyTextTransform("0", "json__a"), IntegerField())
                ).values("x")[0],
                {"x": 1},
            )

            JSONModel.objects.create(json={"c": {"d": "f"}})
            self.assertEqual(
                list(
                    JSONModel.objects.values("json__c__d")
                    .annotate(n=Count("*"))
                    .order_by("json__c__d")
                ),
                [{"json__c__d": "e", "n": 1}, {"json__c__d": "f", "n": 1}],
            )

    def test_lookups(self):
        with json_model() as JSONModel:
            v = {"a": [1, 2, 3], "b": [{"c": 1}, {"c": 2}], "c": {"d": "e"}}
            JSONModel.objects.create(json=v)
            JSONModel.objects.create(
                json={"a": 9, "c": {"d": "f"}, "f": 1.5, "t": True}
            )

            # An object is compared as JSON, insertion order of keys does not
            # matter.
            self.assertTrue(
                JSONModel.objects.filter(
                    json={"c": {"d": "e"}, "b": [{"c": 1}, {"c": 2}], "a": [1, 2, 3]}
                ).exists()
            )
            self.assertEqual(
                JSONModel.objects.filter(json__in=[v, {"a": 0}]).count(), 1
            )
            self.assertTrue(JSONModel.objects.filter(json__a=[1, 2, 3]).exists())
            self.assertTrue(JSONModel.objects.filter(json__b__0__c=1).exists())
            self.assertTrue(JSONModel.objects.filter(json__c__d="e").exists())
            self.assertTrue(JSONModel.objects.filter(json__c={"d": "e"}).exists())
            self.assertTrue(
                JSONModel.objects.filter(json__b=[{"c": 1}, {"c": 2}]).exists()
            )
            # Values are compared in their type, an array is not its own text.
            self.assertFalse(JSONModel.objects.filter(json__a="[1, 2, 3]").exists())
            self.assertFalse(JSONModel.objects.filter(json__z="anything").exists())

            self.assertEqual(JSONModel.objects.filter(json__a__gt=5).count(), 1)
            self.assertEqual(JSONModel.objects.filter(json__a__lt=5).count(), 0)
            self.assertEqual(
                JSONModel.objects.filter(json__c__d__in=["e", "f"]).count(), 2
            )
            self.assertEqual(
                JSONModel.objects.filter(json__c__in=[{"d": "f"}]).count(), 1
            )
            self.assertEqual(JSONModel.objects.filter(json__a__gte=9).count(), 1)
            self.assertEqual(JSONModel.objects.filter(json__a__lte=9).count(), 1)
            # A path is cast to the clickhouse type of the value it is compared
            # with, one of Bool, Int64, Float64 and String.
            self.assertEqual(JSONModel.objects.filter(json__t__gte=True).count(), 1)
            self.assertEqual(JSONModel.objects.filter(json__f__gt=1.0).count(), 1)
            self.assertEqual(JSONModel.objects.filter(json__c__d__gte="e").count(), 2)

            # A path which follows an array index is compared through its text.
            self.assertEqual(JSONModel.objects.filter(json__b__0__c__gt=0).count(), 1)
            self.assertEqual(
                JSONModel.objects.filter(json__b__0__c__in=[1, 5]).count(), 1
            )

            # Lookups django compiles itself, against a path read as text.
            for lookup, value in [
                ("startswith", "e"),
                ("istartswith", "E"),
                ("icontains", "E"),
                ("iexact", "E"),
                ("endswith", "e"),
                ("iendswith", "E"),
                ("regex", "^e$"),
                ("iregex", "^E$"),
            ]:
                with self.subTest(lookup=lookup):
                    self.assertEqual(
                        JSONModel.objects.filter(
                            **{"json__c__d__%s" % lookup: value}
                        ).count(),
                        1,
                    )
            self.assertEqual(JSONModel.objects.filter(json__z__isnull=True).count(), 2)

            # An empty in, an in holding an expression, and a comparison with an
            # expression are left to django.
            self.assertEqual(JSONModel.objects.filter(json__a__in=[]).count(), 0)
            self.assertEqual(
                JSONModel.objects.filter(
                    json__c__d__in=["zz", F("json__c__d")]
                ).count(),
                2,
            )
            self.assertEqual(
                JSONModel.objects.filter(json__c__d=F("json__c__d")).count(), 2
            )
            self.assertEqual(
                JSONModel.objects.filter(json__a__gt=F("json__a")).count(), 0
            )

            # A path is compared with a JSON value by reading it as text too.
            value = Value({"d": "e"}, models.JSONField())
            self.assertEqual(JSONModel.objects.filter(json__c=value).count(), 1)
            self.assertEqual(JSONModel.objects.filter(json__c__in=[value]).count(), 1)
