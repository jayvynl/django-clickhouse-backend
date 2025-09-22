from django.db.models import Q
from django.test import TestCase

from clickhouse_backend.models import (
    anyLast,
    uniq,
    uniqCombined,
    uniqCombined64,
    uniqExact,
    uniqHLL12,
    uniqTheta,
)
from clickhouse_backend.models.aggregates import ArgMax

from .models import WatchSeries


class AggregatesTestCase(TestCase):
    expected_result_without_star = [
        {"show": "Bridgerton", "episode": "S1E1", "uid_count": 4},
        {"show": "Bridgerton", "episode": "S1E2", "uid_count": 2},
        {"show": "Game of Thrones", "episode": "S1E1", "uid_count": 3},
        {"show": "Game of Thrones", "episode": "S1E2", "uid_count": 1},
    ]

    expected_result_with_star = [
        {"show": "Bridgerton", "episode": "S1E1", "uid_count": 6},
        {"show": "Bridgerton", "episode": "S1E2", "uid_count": 3},
        {"show": "Game of Thrones", "episode": "S1E1", "uid_count": 9},
        {"show": "Game of Thrones", "episode": "S1E2", "uid_count": 1},
    ]

    expected_result_any_last = [
        {"uid": "alice", "user_last_watched_show": "Game of Thrones"},
        {"uid": "bob", "user_last_watched_show": "Bridgerton"},
        {"uid": "carol", "user_last_watched_show": "Bridgerton"},
        {"uid": "dan", "user_last_watched_show": "Bridgerton"},
        {"uid": "erin", "user_last_watched_show": "Game of Thrones"},
    ]

    @classmethod
    def setUpTestData(cls):
        data_list = [
            {
                "date": "2022-05-19",
                "user": "alice",
                "show": "Game of Thrones",
                "episode": "S1E1",
            },
            {
                "date": "2022-05-19",
                "user": "alice",
                "show": "Game of Thrones",
                "episode": "S1E2",
            },
            {
                "date": "2022-05-19",
                "user": "alice",
                "show": "Game of Thrones",
                "episode": "S1E1",
            },
            {
                "date": "2022-05-19",
                "user": "bob",
                "show": "Bridgerton",
                "episode": "S1E1",
            },
            {
                "date": "2022-05-20",
                "user": "alice",
                "show": "Game of Thrones",
                "episode": "S1E1",
            },
            {
                "date": "2022-05-20",
                "user": "carol",
                "show": "Bridgerton",
                "episode": "S1E2",
            },
            {
                "date": "2022-05-20",
                "user": "dan",
                "show": "Bridgerton",
                "episode": "S1E1",
            },
            {
                "date": "2022-05-21",
                "user": "alice",
                "show": "Game of Thrones",
                "episode": "S1E1",
            },
            {
                "date": "2022-05-21",
                "user": "carol",
                "show": "Bridgerton",
                "episode": "S1E1",
            },
            {
                "date": "2022-05-21",
                "user": "erin",
                "show": "Game of Thrones",
                "episode": "S1E1",
            },
            {
                "date": "2022-05-21",
                "user": "alice",
                "show": "Bridgerton",
                "episode": "S1E1",
            },
            {
                "date": "2022-05-22",
                "user": "bob",
                "show": "Game of Thrones",
                "episode": "S1E1",
            },
            {
                "date": "2022-05-22",
                "user": "bob",
                "show": "Bridgerton",
                "episode": "S1E1",
            },
            {
                "date": "2022-05-22",
                "user": "carol",
                "show": "Bridgerton",
                "episode": "S1E2",
            },
            {
                "date": "2022-05-22",
                "user": "bob",
                "show": "Bridgerton",
                "episode": "S1E1",
            },
            {
                "date": "2022-05-22",
                "user": "erin",
                "show": "Game of Thrones",
                "episode": "S1E1",
            },
            {
                "date": "2022-05-22",
                "user": "erin",
                "show": "Bridgerton",
                "episode": "S1E2",
            },
            {
                "date": "2022-05-23",
                "user": "erin",
                "show": "Game of Thrones",
                "episode": "S1E1",
            },
            {
                "date": "2022-05-23",
                "user": "alice",
                "show": "Game of Thrones",
                "episode": "S1E1",
            },
        ]

        # Create a list of WatchSeries objects
        watch_series_list = [
            WatchSeries(
                date_id=item["date"],
                uid=item["user"],
                show=item["show"],
                episode=item["episode"],
            )
            for item in data_list
        ]

        # Use bulk_create to insert the list of objects in a single query
        WatchSeries.objects.bulk_create(watch_series_list)

    def test_argMax(self):
        result = (
            WatchSeries.objects.values("show")
            .annotate(episode=ArgMax("episode", "date_id"))
            .order_by("show")
        )

        expected_result = [
            {"show": "Bridgerton", "episode": "S1E1"},
            {"show": "Game of Thrones", "episode": "S1E1"},
        ]

        self.assertQuerysetEqual(result, expected_result, transform=dict)

    def _test_uniq(self, cls_uniq):
        result = (
            WatchSeries.objects.values("show", "episode")
            .annotate(uid_count=cls_uniq("*"))
            .order_by("show", "episode")
        )

        self.assertQuerysetEqual(result, self.expected_result_with_star, transform=dict)

    def _test_uniq_mix_field_star(self, cls_uniq):
        result = (
            WatchSeries.objects.values("show", "episode")
            .annotate(uid_count=cls_uniq("date_id", "*", "uid"))
            .order_by("show", "episode")
        )

        self.assertQuerysetEqual(result, self.expected_result_with_star, transform=dict)

    def _test_uniq_with_filter(self, cls_uniq):
        expected_result = [
            {"show": "Bridgerton", "episode": "S1E1", "uid_count": 6},
            {"show": "Bridgerton", "episode": "S1E2", "uid_count": 0},
            {"show": "Game of Thrones", "episode": "S1E1", "uid_count": 9},
            {"show": "Game of Thrones", "episode": "S1E2", "uid_count": 0},
        ]
        result = (
            WatchSeries.objects.values("show", "episode")
            .annotate(uid_count=cls_uniq("*", filter=Q(episode="S1E1")))
            .order_by("show", "episode")
        )
        self.assertQuerysetEqual(result, expected_result, transform=dict)

    def _test_uniq_without_star(self, cls_uniq):
        result = (
            WatchSeries.objects.values("show", "episode")
            .annotate(uid_count=cls_uniq("uid"))
            .order_by("show", "episode")
        )

        self.assertQuerysetEqual(
            result, self.expected_result_without_star, transform=dict
        )

    def _test(self, cls_uniq):
        self._test_uniq(cls_uniq)
        self._test_uniq_mix_field_star(cls_uniq)
        self._test_uniq_with_filter(cls_uniq)
        self._test_uniq_without_star(cls_uniq)

    def test_uniq(self):
        self._test(uniq)

    def test_uniqexact(self):
        self._test(uniqExact)

    def test_uniqcombined(self):
        self._test(uniqCombined)

    def test_uniqcombined64(self):
        self._test(uniqCombined64)

    def test_uniqhll12(self):
        self._test(uniqHLL12)

    def test_uniqtheta(self):
        self._test(uniqTheta)

    def test_anylast(self):
        result = (
            WatchSeries.objects.values("uid")
            .annotate(user_last_watched_show=anyLast("show"))
            .order_by("uid")
        )

        self.assertQuerysetEqual(result, self.expected_result_any_last, transform=dict)
