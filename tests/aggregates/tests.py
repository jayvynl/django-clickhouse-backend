from django.db.models import Q
from django.test import TestCase

from clickhouse_backend.models import (
    uniq,
    uniqCombined,
    uniqCombined64,
    uniqExact,
    uniqHLL12,
    uniqTheta,
)

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

    def _test_uniq(self, cls_uniq):
        result = (
            WatchSeries.objects.all()
            .values("show", "episode")
            .annotate(uid_count=cls_uniq("*"))
            .order_by("show", "episode")
        )

        self.assertQuerysetEqual(result, self.expected_result_with_star, transform=dict)

    def _test_uniq_with_filter(self, cls_uniq):
        with self.assertRaises(ValueError):
            WatchSeries.objects.values("show", "episode").annotate(
                uid_count=cls_uniq("*", filter=Q(episode="S1E1"))
            ).order_by("show", "episode")

    def _test_uniq_without_star(self, cls_uniq):
        result = (
            WatchSeries.objects.all()
            .values("show", "episode")
            .annotate(uid_count=cls_uniq("uid"))
            .order_by("show", "episode")
        )

        self.assertQuerysetEqual(
            result, self.expected_result_without_star, transform=dict
        )

    def test_uniqexact(self):
        self._test_uniq(uniqExact)
        self._test_uniq_with_filter(uniqExact)
        self._test_uniq_without_star(uniqExact)

    def test_uniq(self):
        self._test_uniq(uniq)
        self._test_uniq_with_filter(uniq)
        self._test_uniq_without_star(uniq)

    def test_uniqcombined(self):
        self._test_uniq(uniqCombined)
        self._test_uniq_with_filter(uniqCombined)
        self._test_uniq_without_star(uniqCombined)

    def test_uniqcombined64(self):
        self._test_uniq(uniqCombined64)
        self._test_uniq_with_filter(uniqCombined64)
        self._test_uniq_without_star(uniqCombined64)

    def test_uniqhll12(self):
        self._test_uniq(uniqHLL12)
        self._test_uniq_with_filter(uniqHLL12)
        self._test_uniq_without_star(uniqHLL12)

    def test_uniqtheta(self):
        self._test_uniq(uniqTheta)
        self._test_uniq_with_filter(uniqTheta)
        self._test_uniq_without_star(uniqTheta)
