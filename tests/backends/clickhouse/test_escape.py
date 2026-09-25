import datetime
import enum
import ipaddress
import uuid

from django.test import SimpleTestCase

from clickhouse_backend.driver.escape import escape_param, escape_params


class Color(enum.Enum):
    RED = "re'd"
    ADDRESS = ipaddress.IPv4Address("1.2.3.4")


class EscapeParamTests(SimpleTestCase):
    def test_datetime(self):
        naive = datetime.datetime(2024, 1, 2, 3, 4, 5, 678901)
        self.assertEqual(escape_param(naive, {}), naive.timestamp())
        aware = naive.replace(tzinfo=datetime.timezone.utc)
        self.assertEqual(escape_param(aware, {}), "'2024-01-02 03:04:05.678901'")
        self.assertEqual(
            escape_param(aware.replace(microsecond=0), {}), "'2024-01-02 03:04:05'"
        )

    def test_datetime_aware_non_utc(self):
        tz = datetime.timezone(datetime.timedelta(hours=5))
        aware = datetime.datetime(2024, 1, 2, 3, 4, 5, 678901, tzinfo=tz)
        # 2024-01-02 03:04:05+05:00 == 2024-01-01 22:04:05 UTC
        self.assertEqual(escape_param(aware, {}), "'2024-01-01 22:04:05.678901'")

    def test_collections(self):
        self.assertEqual(escape_param([1, "a"], {}), "[1,'a']")
        # A one element tuple is tuple(x), clickhouse-driver renders (x), which
        # is just x.
        self.assertEqual(escape_param((1,), {}), "tuple(1)")
        self.assertEqual(escape_param({"a": 1}, {}), "map('a',1)")

    def test_collections_escape_elements_here_too(self):
        value = [ipaddress.IPv6Address("::1"), b"x", (2,)]
        self.assertEqual(escape_param(value, {}), "['::1','x',tuple(2)]")

    def test_enum(self):
        self.assertEqual(escape_param(Color.RED, {}), "'re\\'d'")
        self.assertEqual(escape_param(Color.ADDRESS, {}), "'1.2.3.4'")

    def test_ip_address(self):
        self.assertEqual(
            escape_param(ipaddress.IPv4Address("1.2.3.4"), {}), "'1.2.3.4'"
        )
        self.assertEqual(escape_param(ipaddress.IPv6Address("::1"), {}), "'::1'")

    def test_binary(self):
        self.assertEqual(escape_param(b"x", {}), "'x'")
        self.assertEqual(escape_param(b"\x00F '\xfe", {}), "'\\x00F \\'\\xfe'")

    def test_delegated_to_clickhouse_driver(self):
        self.assertEqual(escape_param(None, {}), "NULL")
        self.assertEqual(escape_param(datetime.date(2024, 1, 2), {}), "'2024-01-02'")
        self.assertEqual(escape_param(datetime.time(3, 4, 5), {}), "'03:04:05'")
        self.assertEqual(escape_param("a'b", {}), "'a\\'b'")
        value = uuid.UUID("12345678-1234-5678-1234-567812345678")
        self.assertEqual(escape_param(value, {}), "'%s'" % value)
        self.assertEqual(escape_param(1, {}), 1)


class EscapeParamsTests(SimpleTestCase):
    def test_params(self):
        # django passes a sequence, clickhouse-driver only takes a dict.
        self.assertEqual(escape_params(["a", 1], {}), ("'a'", 1))
        self.assertEqual(escape_params({"x": "a"}, {}), {"x": "'a'"})
