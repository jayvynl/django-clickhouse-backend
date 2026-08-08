import re
import utils
from functools import partial
from unittest import skipUnless
from io import StringIO

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from clickhouse_backend import compat
from clickhouse_backend.management.commands.inspectdb import Command

JSON_TABLE = "inspectdb_jsoncolumntypes"
json_table = partial(utils.json_model, "inspectdb", JSON_TABLE)


class InspectDBTestCase(TestCase):
    def make_field_type_asserter(self):
        """
        Call inspectdb and return a function to validate a field type in its
        output.
        """
        out = StringIO()
        call_command("inspectdb", "inspectdb_columntypes", stdout=out)
        output = out.getvalue()

        def assertFieldType(name, definition):
            out_def = re.search(r"^\s*%s = (models.*)$" % name, output, re.MULTILINE)[1]
            self.assertEqual(definition, out_def)

        return assertFieldType

    def test_field_types(self):
        """Test introspection of various Django field types"""
        assertFieldType = self.make_field_type_asserter()
        for t in [
            "Int8",
            "UInt8",
            "Int16",
            "UInt16",
            "Int32",
            "UInt32",
            "Int64",
            "UInt64",
            "Int128",
            "UInt128",
            "Int256",
            "UInt256",
            "Float32",
            "Float64",
            "String",
            "UUID",
            "Date",
            "Date32",
            "DateTime",
            "DateTime64",
            "IPv4",
            "IPv6",
        ]:
            assertFieldType(t.lower(), f"models.{t}Field()")
        assertFieldType(
            "decimal", "models.DecimalField(max_digits=38, decimal_places=19)"
        )
        assertFieldType("bool_field", "models.BoolField()")
        assertFieldType("fixed_string", "models.FixedStringField(max_bytes=10)")
        assertFieldType("enum", "models.Enum8Field(choices=[(1, '我'), (2, b'\\x90')])")
        for t in [
            "Enum8",
            "Enum16",
        ]:
            assertFieldType(
                t.lower(), f"models.{t}Field(choices=[(1, '我'), (2, b'\\x90')])"
            )
        assertFieldType("generic_ip", "models.IPv6Field()")
        assertFieldType("array", "models.ArrayField(models.Int8Field())")
        assertFieldType(
            "tuple_field",
            "models.TupleField([models.Int8Field(), models.StringField()])",
        )
        assertFieldType(
            "map_field",
            "models.MapField(models.FixedStringField(low_cardinality=True, max_bytes=10), models.TupleField([models.Int8Field(low_cardinality=True, null=True, blank=True), models.ArrayField(models.Int8Field(low_cardinality=True, null=True, blank=True))]))",
        )

    @skipUnless(
        compat.dj_ge42,
        "https://docs.djangoproject.com/en/4.2/releases/4.2/#comments-on-columns-and-tables",
    )
    def test_db_comments(self):
        out = StringIO()
        call_command("inspectdb", "inspectdb_dbcomment", stdout=out)
        output = out.getvalue()
        self.assertIn(
            "rank = models.Int32Field(db_comment=\"'Rank' column comment\")", output
        )
        self.assertIn("        db_table_comment = 'Custom table comment'", output)


class JsonHintsTests(SimpleTestCase):
    # Every column type here is one clickhouse renders into system.columns.type.

    def assertFieldType(self, column_type, definition):
        generator = Command().inspect_field_type(column_type)
        parts = []
        while True:
            try:
                parts.append(next(generator))
            except StopIteration as stop:
                self.assertEqual(stop.value, "")
                break
        self.assertEqual("".join(parts), definition)

    def test_no_hint(self):
        self.assertFieldType("JSON", "models.JSONField()")

    def test_max_dynamic(self):
        self.assertFieldType(
            "JSON(max_dynamic_types=4, max_dynamic_paths=8)",
            "models.JSONField(max_dynamic_types=4, max_dynamic_paths=8)",
        )

    def test_paths(self):
        self.assertFieldType(
            "JSON(`a.b` UInt32, z Tuple(String, Int8), SKIP `a.c`, SKIP REGEXP 'x,y')",
            "models.JSONField(typed_paths={'a.b': 'UInt32', "
            "'z': 'Tuple(String, Int8)'}, skip_paths=['a.c'], skip_regexps=['x,y'])",
        )

    def test_quoting(self):
        self.assertFieldType(
            r"JSON(SKIP `x\`y`, SKIP REGEXP 'it\'s')",
            "models.JSONField(skip_paths=['x`y'], skip_regexps=[\"it's\"])",
        )

    def test_nested(self):
        self.assertFieldType(
            "Nullable(JSON(max_dynamic_paths=8))",
            "models.JSONField(null=True, blank=True, max_dynamic_paths=8)",
        )
        self.assertFieldType(
            "Array(JSON(SKIP `a`))",
            "models.ArrayField(models.JSONField(skip_paths=['a']))",
        )


class JsonInspectDBTests(TestCase):
    def assertJsonField(self, definition, **kwargs):
        with json_table(**kwargs):
            out = StringIO()
            call_command("inspectdb", JSON_TABLE, stdout=out)
            out_def = re.search(r"^\s*json = (models.*)$", out.getvalue(), re.MULTILINE)
            self.assertEqual(out_def[1], definition)

    def test_json(self):
        self.assertJsonField("models.JSONField()")

    def test_nullable(self):
        self.assertJsonField("models.JSONField(null=True, blank=True)", null=True)

    def test_hints(self):
        self.assertJsonField(
            "models.JSONField(max_dynamic_types=4, max_dynamic_paths=8, "
            "typed_paths={'a.b': 'UInt32'}, skip_paths=['a.c'], "
            "skip_regexps=['tmp[0-9]'])",
            max_dynamic_types=4,
            max_dynamic_paths=8,
            typed_paths={"a.b": "UInt32"},
            skip_paths=["a.c"],
            skip_regexps=["tmp[0-9]"],
        )

    def test_quoted_hints(self):
        self.assertJsonField(
            "models.JSONField(typed_paths={'a b': 'Tuple(String, Int8)'}, "
            "skip_paths=['x`y'], skip_regexps=[\"it's\"])",
            typed_paths={"a b": "Tuple(String, Int8)"},
            skip_paths=["x`y"],
            skip_regexps=["it's"],
        )
