import re
from unittest import skipUnless
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from clickhouse_backend import compat


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
            "JSON",
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
