import utils
from functools import partial

from django.db import DatabaseError, NotSupportedError, connection
from django.db.models import F, Value
from django.db.models.fields.json import KeyTransform
from django.test import TestCase

from clickhouse_backend import models

json_model = partial(utils.json_model, "clickhouse_functions")


class JsonFunctionTests(TestCase):
    def test_paths(self):
        with json_model() as JSONModel:
            o = JSONModel.objects.create(json={"a": {"b": 1}, "c": "x", "d": [1, 2]})
            qs = JSONModel.objects.filter(id=o.id)
            self.assertEqual(
                qs.values_list(models.JSONAllPaths("json"), flat=True)[0],
                ["a.b", "c", "d"],
            )
            self.assertEqual(
                qs.values_list(models.JSONAllPathsWithTypes("json"), flat=True)[0],
                {"a.b": "Int64", "c": "String", "d": "Array(Nullable(Int64))"},
            )

    def test_shared_data_paths(self):
        # Everything past max_dynamic_paths is stored together instead of as a
        # sub-column of its own. The limit only applies to a value clickhouse
        # parses itself, so the row cannot be written through the ORM.
        with json_model(max_dynamic_paths=1) as JSONModel:
            with connection.cursor() as cursor:
                cursor.execute(
                    'INSERT INTO "%s" (json) VALUES (%%s)' % JSONModel._meta.db_table,
                    ['{"a": 1, "b": 2, "c": 3}'],
                )
            qs = JSONModel.objects.annotate(shared=models.JSONSharedDataPaths("json"))
            self.assertEqual(qs.values_list("shared", flat=True)[0], ["b", "c"])
            self.assertTrue(qs.filter(shared__len=2, shared__any="b").exists())

    def test_all_values(self):
        with json_model() as JSONModel:
            o = JSONModel.objects.create(json={"a": 1, "b": "x"})
            qs = JSONModel.objects.filter(id=o.id).annotate(
                values=models.JSONAllValues("json")
            )
            self.assertEqual(qs.values_list("values", flat=True)[0], ["1", "x"])
            self.assertTrue(qs.filter(values__len=2, values__any="x").exists())

    def test_dynamic_type(self):
        with json_model() as JSONModel:
            JSONModel.objects.create(json={"a": 1, "n": {"b": "x"}, "d": [1, 2]})
            JSONModel.objects.create(json={"a": "text"})

            def types(path):
                expression = models.dynamicType(path)
                return sorted(JSONModel.objects.values_list(expression, flat=True))

            self.assertEqual(types(F("json__a")), ["Int64", "String"])
            # A nested object is not a value of the path itself, and a path which
            # is absent has no type at all.
            self.assertEqual(types(F("json__n")), ["None", "None"])
            self.assertEqual(types(KeyTransform("b", "json__n")), ["None", "String"])

    def test_dynamic_type_of_an_expression(self):
        # Anything but a key transform is left to django to compile, and only a
        # Dynamic has a type for clickhouse to report.
        with json_model() as JSONModel:
            JSONModel.objects.create(json={"a": 1})
            with self.assertRaises(DatabaseError):
                list(
                    JSONModel.objects.values_list(
                        models.dynamicType(F("json")), flat=True
                    )
                )

    def test_dynamic_type_after_an_array_index(self):
        with json_model() as JSONModel:
            JSONModel.objects.create(json={"d": [{"e": 1}]})
            with self.assertRaisesMessage(
                NotSupportedError,
                "cannot read a JSON path which follows an array index",
            ):
                list(
                    JSONModel.objects.values_list(
                        models.dynamicType(F("json__d__0__e")), flat=True
                    )
                )

    def test_string_functions(self):
        with json_model() as JSONModel:
            o = JSONModel.objects.create(json={"a": [1, 2, 3]})
            self.assertEqual(
                JSONModel.objects.filter(id=o.id)
                .annotate(
                    text=models.toJSONString("json"),
                    valid=models.isValidJSON(Value("{")),
                    length=models.JSONLength(models.toJSONString("json"), Value("a")),
                    merged=models.JSONMergePatch(
                        Value('{"a": 1}'), Value('{"a": 2, "b": 3}')
                    ),
                )
                .values("text", "valid", "length", "merged")[0],
                {
                    "text": '{"a":[1,2,3]}',
                    "valid": False,
                    "length": 3,
                    "merged": '{"a":2,"b":3}',
                },
            )

    def test_output_fields(self):
        # A lookup is only reachable through the output_field of the function it
        # is applied to, and the rhs is adapted by that field, so filtering on an
        # annotation is what proves the field of each one.
        with json_model() as JSONModel:
            JSONModel.objects.create(json={"a": {"b": 1}, "c": "x"})
            qs = JSONModel.objects.annotate(
                paths=models.JSONAllPaths("json"),
                types=models.JSONAllPathsWithTypes("json"),
                text=models.toJSONString("json"),
                valid=models.isValidJSON(models.toJSONString("json")),
                length=models.JSONLength(models.toJSONString("json")),
                merged=models.JSONMergePatch(
                    models.toJSONString("json"), Value('{"d": 4}')
                ),
                type_of_b=models.dynamicType(KeyTransform("b", "json__a")),
            )
            for lookup, value in [
                # ArrayField(StringField)
                ("paths__len", 2),
                ("paths__exact", ["a.b", "c"]),
                ("paths__contains", ["a.b"]),
                ("paths__overlap", ["c", "zz"]),
                ("paths__any", "c"),
                # MapField(StringField, StringField)
                ("types__len", 2),
                ("types__has_key", "a.b"),
                ("types__keys__any", "c"),
                ("types__values__any", "String"),
                # StringField. A comparison with a value that is not a number is
                # what rejects a numeric field, get_prep_value() raises on it.
                ("text__contains", '"c":"x"'),
                ("text__gt", "{"),
                ("merged__endswith", '"d":4}'),
                ("merged__gt", "{"),
                ("type_of_b__exact", "Int64"),
                # BoolField, and a UInt64Field which orders 2 before 10 rather
                # than after it as the text of a number would.
                ("valid__exact", True),
                ("length__lt", 10),
            ]:
                with self.subTest(lookup=lookup):
                    self.assertTrue(qs.filter(**{lookup: value}).exists())
            # A comparison alone does not tell a number from its text, clickhouse
            # converts the one to the other. Arithmetic does: django refuses to
            # combine a StringField with an IntegerField.
            self.assertTrue(
                qs.annotate(longer=F("length") + Value(1)).filter(longer=3).exists()
            )
