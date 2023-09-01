from django.db import connection, migrations
from django.db.migrations.state import ProjectState
from django.test import TestCase

from clickhouse_backend import models

from .models import DistributedStudent, Student
from .test_base import OperationTestBase


class TestDistributed(TestCase):
    databases = {"default", "s1r2", "s2r1", "other"}

    def test_distributed_can_see_underlying_table(self):
        Student.objects.create(name="Jack", score=90)
        assert DistributedStudent.objects.filter(name="Jack", score=90).exists()

    def test_write_distributed(self):
        for i in range(10):
            DistributedStudent.objects.create(name=f"Student{i}", score=i * 10)
        assert DistributedStudent.objects.count() == 10
        assert DistributedStudent.objects.using("s1r2").count() == 10
        assert DistributedStudent.objects.using("s2r1").count() == 10
        assert Student.objects.count() == Student.objects.using("s1r2").count()
        assert (
            Student.objects.using("s1r2").count()
            + Student.objects.using("s2r1").count()
            == 10
        )


class OperationTests(OperationTestBase):
    def test_create_model(self):
        """
        Tests the CreateModel operation.
        Most other tests use this operation as part of setup, so check failures
        here first.
        """
        create_replicated = migrations.CreateModel(
            "Pony",
            [
                ("id", models.Int64Field(primary_key=True)),
                ("pink", models.Int32Field(default=1)),
            ],
            options={
                "engine": models.ReplacingMergeTree(order_by="id"),
                "cluster": "cluster",
            },
        )
        create_distributed = migrations.CreateModel(
            "PonyDistributed",
            [
                ("id", models.Int64Field(primary_key=True)),
                ("pink", models.Int32Field(default=1)),
            ],
            options={
                "engine": models.Distributed(
                    "cluster", models.currentDatabase(), "test_crmo_pony"
                ),
                "cluster": "cluster",
            },
        )

        # Test the state alteration
        state0 = ProjectState()
        state1 = state0.clone()
        create_replicated.state_forwards("test_crmo", state1)

        # Test create replicated.
        self.assertTableNotExistsCluster("test_crmo_pony")
        with connection.schema_editor() as editor:
            create_replicated.database_forwards("test_crmo", editor, state0, state1)
        self.assertTableExistsCluster("test_crmo_pony")
        # Test create distributed.
        state2 = state1.clone()
        create_distributed.state_forwards("test_crmo", state2)
        self.assertTableNotExistsCluster("test_crmo_ponydistributed")
        with connection.schema_editor() as editor:
            create_distributed.database_forwards("test_crmo", editor, state1, state2)
        self.assertTableExistsCluster("test_crmo_ponydistributed")
        # And test reversal
        with connection.schema_editor() as editor:
            create_distributed.database_backwards("test_crmo", editor, state2, state1)
            self.assertTableExistsCluster("test_crmo_pony")
            self.assertTableNotExistsCluster("test_crmo_ponydistributed")
            create_replicated.database_backwards("test_crmo", editor, state1, state0)
            self.assertTableNotExistsCluster("test_crmo_pony")
            self.assertTableNotExistsCluster("test_crmo_ponydistributed")

    def test_rename_model(self):
        """
        Tests the RenameModel operation.
        """
        project_state = self.set_up_distributed_model("test_rnmo", related_model=True)
        # Test the state alteration
        operation = migrations.RenameModel("Pony", "Horse")
        self.assertEqual(operation.describe(), "Rename model Pony to Horse")
        self.assertEqual(operation.migration_name_fragment, "rename_pony_horse")
        # Test initial state and database
        self.assertIn(("test_rnmo", "pony"), project_state.models)
        self.assertNotIn(("test_rnmo", "horse"), project_state.models)
        self.assertTableExistsCluster("test_rnmo_pony")
        self.assertTableNotExistsCluster("test_rnmo_horse")

        # Migrate forwards
        new_state = project_state.clone()
        new_state = self.apply_operations("test_rnmo", new_state, [operation])
        # Test new state and database
        self.assertNotIn(("test_rnmo", "pony"), new_state.models)
        self.assertIn(("test_rnmo", "horse"), new_state.models)
        # RenameModel also repoints all incoming FKs and M2Ms
        self.assertEqual(
            new_state.models["test_rnmo", "rider"].fields["pony"].remote_field.model,
            "test_rnmo.Horse",
        )
        self.assertTableNotExistsCluster("test_rnmo_pony")
        self.assertTableExistsCluster("test_rnmo_horse")

        # Migrate backwards
        project_state = self.unapply_operations("test_rnmo", project_state, [operation])
        # Test original state and database
        self.assertIn(("test_rnmo", "pony"), project_state.models)
        self.assertNotIn(("test_rnmo", "horse"), project_state.models)
        self.assertEqual(
            project_state.models["test_rnmo", "rider"]
            .fields["pony"]
            .remote_field.model,
            "Pony",
        )
        self.assertTableExistsCluster("test_rnmo_pony")
        self.assertTableNotExistsCluster("test_rnmo_horse")

        # Test the state alteration
        operation = migrations.RenameModel("PonyDistributed", "HorseDistributed")
        self.assertEqual(
            operation.describe(), "Rename model PonyDistributed to HorseDistributed"
        )
        self.assertEqual(
            operation.migration_name_fragment, "rename_ponydistributed_horsedistributed"
        )
        # Test initial state and database
        self.assertIn(("test_rnmo", "ponydistributed"), project_state.models)
        self.assertNotIn(("test_rnmo", "horsedistributed"), project_state.models)
        self.assertTableExistsCluster("test_rnmo_ponydistributed")
        self.assertTableNotExistsCluster("test_rnmo_horsedistributed")

        # Migrate forwards
        new_state = project_state.clone()
        new_state = self.apply_operations("test_rnmo", new_state, [operation])
        # Test new state and database
        self.assertNotIn(("test_rnmo", "ponydistributed"), new_state.models)
        self.assertIn(("test_rnmo", "horsedistributed"), new_state.models)
        # RenameModel also repoints all incoming FKs and M2Ms
        self.assertEqual(
            new_state.models["test_rnmo", "riderdistributed"]
            .fields["pony"]
            .remote_field.model,
            "test_rnmo.HorseDistributed",
        )
        self.assertTableNotExistsCluster("test_rnmo_ponydistributed")
        self.assertTableExistsCluster("test_rnmo_horsedistributed")

        # Migrate backwards
        original_state = self.unapply_operations(
            "test_rnmo", project_state, [operation]
        )
        # Test original state and database
        self.assertIn(("test_rnmo", "ponydistributed"), original_state.models)
        self.assertNotIn(("test_rnmo", "horsedistributed"), original_state.models)
        self.assertEqual(
            original_state.models["test_rnmo", "riderdistributed"]
            .fields["pony"]
            .remote_field.model,
            "PonyDistributed",
        )
        self.assertTableExistsCluster("test_rnmo_ponydistributed")
        self.assertTableNotExistsCluster("test_rnmo_horsedistributed")
