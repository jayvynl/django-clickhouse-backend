import re
import time

from clickhouse_driver import client

from .escape import escape_params

insert_pattern = re.compile(r"^\s*insert\s+into.+?values\s*;?$", flags=re.IGNORECASE)


class Client(client.Client):
    def __init__(self, *args, **kwargs):
        # Never mutate the caller's dict, DatabaseWrapper.get_new_connection
        # compares connection parameters to decide whether it can share a
        # connection. A setting given by the caller wins.
        kwargs["settings"] = {
            # https://clickhouse.com/docs/en/sql-reference/data-types/datetime/#usage-remarks
            # The clickhouse-client applies the server time zone by default
            # if a time zone isn’t explicitly set when initializing the data type.
            # To use the client time zone, run clickhouse-client with the --use_client_time_zone parameter.
            "use_client_time_zone": True,
            # A JSON value is read through toJSONString(), which renders an Int64
            # as a string before ClickHouse 25.8, where the default became 0.
            # https://github.com/ClickHouse/ClickHouse/blob/31081d9f05014003321333553bb3e657eb3da168/docs/changelogs/v25.8.1.5101-lts.md?plain=1#L11
            "output_format_json_quote_64bit_integers": 0,
            **(kwargs.get("settings") or {}),
        }
        super().__init__(*args, **kwargs)

    def substitute_params(self, query, params, context):
        escaped = escape_params(params, context)
        return query % escaped

    def execute(
        self,
        query,
        params=None,
        with_column_types=False,
        external_tables=None,
        query_id=None,
        settings=None,
        types_check=False,
        columnar=False,
    ):
        """Support dict params for INSERT queries."""
        start_time = time.time()

        with self.disconnect_on_error(query, settings):
            is_insert = insert_pattern.match(query)

            if is_insert:
                rv = self.process_insert_query(
                    query,
                    params,
                    external_tables=external_tables,
                    query_id=query_id,
                    types_check=types_check,
                    columnar=columnar,
                )
            else:
                rv = self.process_ordinary_query(
                    query,
                    params=params,
                    with_column_types=with_column_types,
                    external_tables=external_tables,
                    query_id=query_id,
                    types_check=types_check,
                    columnar=columnar,
                )
            self.last_query.store_elapsed(time.time() - start_time)
            return rv
