import re
import time

from clickhouse_driver import client

from .escape import escape_params

insert_pattern = re.compile(r'\s*insert\s*into', flags=re.IGNORECASE)


class Client(client.Client):
    def substitute_params(self, query, params, context):
        escaped = escape_params(params, context)
        return query % escaped

    def execute(self, query, params=None, with_column_types=False,
                external_tables=None, query_id=None, settings=None,
                types_check=False, columnar=False):
        """Support dict params for INSERT queries."""
        start_time = time.time()

        with self.disconnect_on_error(query, settings):
            is_insert = insert_pattern.match(query)

            if is_insert:
                rv = self.process_insert_query(
                    query, params, external_tables=external_tables,
                    query_id=query_id, types_check=types_check,
                    columnar=columnar
                )
            else:
                rv = self.process_ordinary_query(
                    query, params=params, with_column_types=with_column_types,
                    external_tables=external_tables,
                    query_id=query_id, types_check=types_check,
                    columnar=columnar
                )
            self.last_query.store_elapsed(time.time() - start_time)
            return rv
