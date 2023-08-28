from django.test import TestCase

from .models import DistributedStudent, Student


class TestDistributed(TestCase):
    def test(self):
        Student.objects.create(name="Jack", score=90)
        assert DistributedStudent.objects.filter(name="Jack", score=90).exists()
        DistributedStudent.objects.create(name="Bob", score=80)
        assert DistributedStudent.objects.count() == 2
