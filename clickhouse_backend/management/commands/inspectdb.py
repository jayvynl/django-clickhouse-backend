import re

from django.core.management.commands.inspectdb import Command as DCommand
from django.db import connections

from clickhouse_backend import compat, models
from clickhouse_backend.utils.encoding import ensure_str


class Command(DCommand):
    def handle_inspection(self, options):
        connection = connections[options["database"]]
        if connection.vendor != "clickhouse":
            return super().handle_inspection(options)
        # 'table_name_filter' is a stealth option
        table_name_filter = options.get("table_name_filter")

        def table2model(table_name):
            return re.sub(r"[^a-zA-Z0-9]", "", table_name.title())

        with connection.cursor() as cursor:
            yield "# This is an auto-generated Django model module."
            yield "# You'll have to do the following manually to clean this up:"
            yield "#   * Rearrange models' order"
            yield "#   * Make sure each model has one field with primary_key=True"
            yield (
                "#   * Remove `managed = False` lines if you wish to allow "
                "Django to create, modify, and delete the table"
            )
            yield (
                "# Feel free to rename the models, but don't rename db_table values or "
                "field names."
            )
            yield "from clickhouse_backend import models"
            known_models = []
            # Determine types of tables and/or views to be introspected.
            types = {"t"}
            if options["include_views"]:
                types.add("v")
            table_info = connection.introspection.get_table_list(cursor)
            table_info = {info.name: info for info in table_info if info.type in types}

            for table_name in options["table"] or sorted(name for name in table_info):
                if table_name_filter is not None and callable(table_name_filter):
                    if not table_name_filter(table_name):
                        continue
                try:
                    table_description = connection.introspection.get_table_description(
                        cursor, table_name
                    )
                except Exception as e:
                    yield f"# Unable to inspect table '{table_name}'"
                    yield f"# The error was: {e}"
                    continue

                model_name = table2model(table_name)
                yield ""
                yield ""
                yield f"class {model_name}(models.ClickhouseModel):"
                known_models.append(model_name)
                used_column_names = []  # Holds column names used in the table so far
                column_to_field_name = {}  # Maps column names to names of model fields

                for row in table_description:
                    column_name = row.name

                    (
                        att_name,
                        extra_params,  # Holds Field parameters such as 'db_column'.
                        comment_notes,  # Holds Field notes, to be displayed in a Python comment.
                    ) = self.normalize_col_name(column_name, used_column_names, False)

                    used_column_names.append(att_name)
                    column_to_field_name[column_name] = att_name

                    # Add comment.
                    if (
                        compat.dj_ge42
                        and connection.features.supports_comments
                        and row.comment
                    ):
                        extra_params["db_comment"] = row.comment

                    if extra_params:
                        param = ", ".join(f"{k}={v!r}" for k, v in extra_params.items())
                    else:
                        param = ""

                    field_define = "".join(
                        self.inspect_field_type(row.type_code, param)
                    )
                    field_desc = f"{att_name} = {field_define}"
                    if comment_notes:
                        field_desc += "  # " + " ".join(comment_notes)
                    yield f"    {field_desc}"

                comment = None
                managed_comment = ""
                info = table_info.get(table_name)
                if info:
                    if info.type == "v":
                        managed_comment = "  # Created from a view. Don't remove."
                    if connection.features.supports_comments:
                        comment = info.comment

                yield ""
                yield "    class Meta:"
                yield f"        managed = False{managed_comment}"
                yield f"        db_table = {table_name!r}"
                if compat.dj_ge42 and comment:
                    yield f"        db_table_comment = {comment!r}"

    def inspect_field_type(self, column_type, param=""):
        column_type = ensure_str(column_type)
        # LowCardinality(Int16)
        if column_type.startswith("LowCardinality"):
            param = self.merge_params(param, "low_cardinality=True")
            remain = yield from self.inspect_field_type(column_type[15:], param)
            return remain[1:]
        # Nullable(Int16)
        elif column_type.startswith("Nullable"):
            param = self.merge_params(param, "null=True", "blank=True")
            remain = yield from self.inspect_field_type(column_type[9:], param)
            return remain[1:]
        # FixedString(20)
        elif column_type.startswith("FixedString"):
            i = 12
            while column_type[i].isdigit():
                i += 1
            param = self.merge_params(param, f"max_bytes={column_type[12:i]}")
            yield f"models.FixedStringField({param})"
            return column_type[i + 1 :]
        # DateTime64(6, 'UTC') or DateTime64(9)
        elif column_type.startswith("DateTime64"):
            if int(column_type[11]) != models.DateTime64Field.DEFAULT_PRECISION:
                param = self.merge_params(param, f"precision={column_type[11]}")
            yield f"models.DateTime64Field({param})"

            if column_type[12] == ",":
                i = 15
                while column_type[i] != "'":
                    i += 1
                return column_type[i + 2 :]
            return column_type[13:]
        # DateTime('UTC') or DateTime
        elif column_type.startswith("DateTime"):
            yield f"models.DateTimeField({param})"
            if len(column_type) > 8 and column_type[8] == "(":
                i = 10
                while column_type[i] != "'":
                    i += 1
                    return column_type[i + 2 :]
            return column_type[8:]
        # Decimal(9, 3)
        elif column_type.startswith("Decimal"):
            i = 8
            while column_type[i].isdigit():
                i += 1
            max_digits = f"max_digits={column_type[8:i]}"
            i += 2
            j = i
            while column_type[i].isdigit():
                i += 1
            decimal_places = f"decimal_places={column_type[j:i]}"
            param = self.merge_params(param, max_digits, decimal_places)
            yield f"models.DecimalField({param})"
            return column_type[i + 1 :]
        # Enum8('a' = 1, 'b' = 2)
        elif column_type.startswith("Enum"):
            i = 4
            while column_type[i].isdigit():
                i += 1
            typ = column_type[:i]
            choices = []
            name, value, remain = self.consume_enum_choice(column_type[i + 1 :])
            choices.append(f"({value}, {name})")
            while remain[0] != ")":
                name, value, remain = self.consume_enum_choice(remain[2:])
                choices.append(f"({value}, {name})")
            param = self.merge_params(param, f"choices=[{', '.join(choices)}]")
            yield f"models.{typ}Field({param})"
            return remain[1:]
        # Array(Tuple(String, Enum8('a' = 1, 'b' = 2)))
        elif column_type.startswith("Array"):
            yield "models.ArrayField("
            remain = yield from self.inspect_field_type(column_type[6:])
            if param:
                yield f", {param}"
            yield ")"
            return remain[1:]
        # Tuple(String, Enum8('a' = 1, 'b' = 2))
        elif column_type.startswith("Tuple"):
            yield "models.TupleField(["
            remain = yield from self.inspect_field_type(column_type[6:])
            while remain[0] == ",":
                yield ", "
                remain = yield from self.inspect_field_type(remain[2:])
            yield "]"
            if param:
                yield f", {param}"
            yield ")"
            return remain[1:]
        # Map(String, Int8)
        elif column_type.startswith("Map"):
            yield "models.MapField("
            remain = yield from self.inspect_field_type(column_type[4:])
            yield ", "
            remain = yield from self.inspect_field_type(remain[2:])
            if param:
                yield f", {param}"
            yield ")"
            return remain[1:]
        # JSON or JSON(max_dynamic_paths=64, `a.b` UInt32, SKIP `a.c`)
        elif column_type.startswith("JSON"):
            remain = column_type[4:]
            if remain.startswith("("):
                hints, remain = self.consume_type_params(remain)
                param = self.merge_params(param, *self.json_hints(hints))
            yield f"models.JSONField({param})"
            return remain

        i = 0
        length = len(column_type)
        while i < length and column_type[i].isalnum():
            i += 1
        yield f"models.{column_type[:i]}Field({param})"
        return column_type[i:]

    def consume_enum_choice(self, s):
        # 'a' = 1
        has_bytes = False
        i = 1
        while True:
            if s[i] == "\\":  # escape char
                if s[i + 1] == "x":
                    has_bytes = True
                i += 2
                continue
            if s[i] == "'":
                break
            i += 1
        i += 1
        name = s[:i]
        # try decoding bytes to utf8 string.
        if has_bytes:
            try:
                decoded = eval(f"b{name}.decode('utf-8')")
            except UnicodeDecodeError:
                name = f"b{name}"
            else:
                name = repr(decoded)

        i += 3
        j = i
        while s[i].isdigit():
            i += 1
        value = s[j:i]
        return name, value, s[i:]

    def consume_quoted(self, s, i):
        """Return the index just after the string quoted by s[i]."""
        quote = s[i]
        i += 1
        while s[i] != quote:
            i += 2 if s[i] == "\\" else 1
        return i + 1

    def consume_type_params(self, s):
        """Split the parameter list ``(a, b)`` at the start of ``s``, and return
        its items and what follows it. A nested list and a quoted string are left
        alone, they may hold a comma of their own.
        """
        items = []
        item = ""
        depth = 1
        i = 1  # s[0] is the opening parenthesis.
        while i < len(s):
            char = s[i]
            if char in "`'":
                end = self.consume_quoted(s, i)
                item += s[i:end]
                i = end
                continue
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if not depth:
                    return [*items, item.strip()], s[i + 1 :]
            if depth == 1 and char == ",":
                items.append(item.strip())
                item = ""
            else:
                item += char
            i += 1
        return items, ""

    def json_hints(self, hints):
        typed_paths = {}
        skip_paths = []
        skip_regexps = []
        for hint in hints:
            if hint.startswith("max_dynamic"):  # max_dynamic_paths=64
                yield hint
            elif hint.startswith("SKIP REGEXP "):  # SKIP REGEXP 'a.*'
                skip_regexps.append(
                    hint[13:-1].replace("\\\\", "\\").replace("\\'", "'")
                )
            elif hint.startswith("SKIP "):  # SKIP `a.c`
                skip_paths.append(self.consume_path(hint[5:])[0])
            else:  # `a.b` UInt32
                path, path_type = self.consume_path(hint)
                typed_paths[path] = path_type
        if typed_paths:
            yield f"typed_paths={typed_paths!r}"
        if skip_paths:
            yield f"skip_paths={skip_paths!r}"
        if skip_regexps:
            yield f"skip_regexps={skip_regexps!r}"

    def consume_path(self, s):
        """Split a path hint into its path and the type following it, if any.

        A path is one identifier, quoted unless it is a plain name: clickhouse
        joins the keys of a nested path with dots and renders it as one.
        """
        if s.startswith("`"):
            end = self.consume_quoted(s, 0)
            path = s[1 : end - 1].replace("\\\\", "\\").replace("\\`", "`")
            return path, s[end + 1 :]
        path, _, path_type = s.partition(" ")
        return path, path_type

    def merge_params(self, *params):
        return ", ".join(filter(None, params))
