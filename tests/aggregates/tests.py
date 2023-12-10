from clickhouse_backend.models import (
    uniq,
    uniqCombined,
    uniqCombined64,
    uniqExact,
    uniqHLL12,
    uniqTheta,
)

from django.test import TestCase

from .models import WatchSeries


class CountTestCase(TestCase):
    expected = [
        {"show": "Bridgerton", "episode": "S1E1", "uid_count": 4},
        {"show": "Bridgerton", "episode": "S1E2", "uid_count": 2},
        {"show": "Game of Thrones", "episode": "S1E1", "uid_count": 3},
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

        for item in data_list:
            # Create a new WatchSeries instance with the data from each dictionary
            WatchSeries.objects.create(
                date_id=item["date"],
                uid=item["user"],
                show=item["show"],
                episode=item["episode"],
            )

    def test_uniqexact(self):
        result = (
            WatchSeries.objects.all()
            .values("show", "episode")
            .annotate(uid_count=uniqExact("uid"))
            .order_by("show", "episode")
        )
        self.assertListEqual(list(result), self.expected)

    def test_uniq(self):
        result = (
            WatchSeries.objects.all()
            .values("show", "episode")
            .annotate(uid_count=uniq("uid"))
            .order_by("show", "episode")
        )
        self.assertListEqual(list(result), self.expected)

    def test_uniq_combined(self):
        result = (
            WatchSeries.objects.all()
            .values("show", "episode")
            .annotate(uid_count=uniqCombined("uid"))
            .order_by("show", "episode")
        )
        self.assertListEqual(list(result), self.expected)

    def test_uniq_combined64(self):
        result = (
            WatchSeries.objects.all()
            .values("show", "episode")
            .annotate(uid_count=uniqCombined64("uid"))
            .order_by("show", "episode")
        )
        self.assertListEqual(list(result), self.expected)

    def test_uniq_hll12(self):
        result = (
            WatchSeries.objects.all()
            .values("show", "episode")
            .annotate(uid_count=uniqHLL12("uid"))
            .order_by("show", "episode")
        )
        self.assertListEqual(list(result), self.expected)

    def test_uniq_theta(self):
        result = (
            WatchSeries.objects.all()
            .values("show", "episode")
            .annotate(uid_count=uniqTheta("uid"))
            .order_by("show", "episode")
        )
        self.assertListEqual(list(result), self.expected)
