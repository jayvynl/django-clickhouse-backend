from django.core.exceptions import FieldDoesNotExist
from django.db import OperationalError, connection, migrations
from django.db import models as django_models
from django.db.migrations.operations.fields import FieldOperation
from django.db.migrations.state import ModelState, ProjectState
from django.db.models.functions import Abs
from django.db.transaction import atomic
from django.test import SimpleTestCase, TestCase, override_settings, skipUnlessDBFeature
from django.test.utils import CaptureQueriesContext

from clickhouse_backend import models

from ..migrations.test_base import OperationTestBase
from .models import DistributedStudent, Student


class TestDistributed(TestCase):
    def test(self):
        Student.objects.create(name="Jack", score=90)
        assert Student.objects.using("s1r2").filter(name="Jack", score=90).exists()
        assert DistributedStudent.objects.filter(name="Jack", score=90).exists()
        for i in range(10):
            DistributedStudent.objects.create(name=f"Student{i}", score=i * 10)
        assert DistributedStudent.objects.count() == 11
        assert DistributedStudent.objects.using("s1r2").count() == 11
        assert DistributedStudent.objects.using("s2r1").count() == 11
        assert (
            Student.objects.using("s1r2").count()
            + Student.objects.using("s2r1").count()
            == 11
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
                "engine": models.ReplacingMergeTree(),
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
        project_state = ProjectState()
        new_state = project_state.clone()
        create_replicated.state_forwards("test_crmo", new_state)

        # Test create replicated.
        self.assertTableNotExistsCluster("test_crmo_pony")
        with connection.schema_editor() as editor:
            create_replicated.database_forwards(
                "test_crmo", editor, project_state, new_state
            )
        self.assertTableExistsCluster("test_crmo_pony")
        # Test create distributed.
        self.assertTableNotExistsCluster("test_crmo_ponydistributed")
        with connection.schema_editor() as editor:
            create_distributed.database_forwards(
                "test_crmo", editor, project_state, new_state
            )
        self.assertTableExistsCluster("test_crmo_ponydistributed")
        # And test reversal
        with connection.schema_editor() as editor:
            create_distributed.database_backwards(
                "test_crmo", editor, new_state, project_state
            )
        self.assertTableNotExistsCluster("test_crmo_pony")
        self.assertTableNotExistsCluster("test_crmo_ponydistributed")

    def test_rename_model(self):
        """
        Tests the RenameModel operation.
        """
        project_state = self.set_up_distributed_model("test_rnmo")
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
            operation.migration_name_fragment, "rename_pony_horsedistributed"
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

    def set_up_distributed_model(
        self,
        app_label,
        index=False,
        related_model=False,
        multicol_index=False,
        index_together=False,
        constraints=None,
        indexes=None,
    ):
        """Creates a test model state and database table."""
        meta_indexes = (
            [
                models.Index(
                    fields=("weight", "pink"),
                    name="weight_pink_idx",
                    type=models.Set(100),
                    granularity=10,
                )
            ]
            if index_together
            else []
        )

        operations = [
            migrations.CreateModel(
                "Pony",
                [
                    ("id", django_models.BigAutoField(primary_key=True)),
                    ("pink", models.Int32Field(default=3)),
                    ("weight", models.Float64Field()),
                ],
                options={
                    "indexes": meta_indexes,
                    "engine": models.ReplacingMergeTree(),
                    "cluster": "cluster",
                },
            ),
            migrations.CreateModel(
                "PonyDistributed",
                [
                    ("id", django_models.BigAutoField(primary_key=True)),
                    ("pink", models.Int32Field(default=3)),
                    ("weight", models.Float64Field()),
                ],
                options={
                    "indexes": meta_indexes,
                    "engine": models.Distributed(
                        "cluster", models.currentDatabase(), f"{app_label}_pony"
                    ),
                    "cluster": "cluster",
                },
            ),
        ]

        for name in ["pony", "ponydistributed"]:
            if index:
                operations.append(
                    migrations.AddIndex(
                        name,
                        models.Index(
                            fields=["pink"],
                            name=f"{name}_pink_idx",
                            type=models.Set(100),
                            granularity=10,
                        ),
                    )
                )
            if multicol_index:
                operations.append(
                    migrations.AddIndex(
                        name,
                        models.Index(
                            fields=["pink", "weight"],
                            name=f"{name}_test_idx",
                            type=models.Set(100),
                            granularity=10,
                        ),
                    )
                )
            if indexes:
                for index in indexes:
                    operations.append(migrations.AddIndex(name, index))
            if constraints:
                for constraint in constraints:
                    operations.append(migrations.AddConstraint(name, constraint))
        if related_model:
            operations.append(
                migrations.CreateModel(
                    "Rider",
                    [
                        ("id", django_models.BigAutoField(primary_key=True)),
                        (
                            "pony",
                            django_models.ForeignKey("Pony", django_models.CASCADE),
                        ),
                        (
                            "friend",
                            django_models.ForeignKey(
                                "self", django_models.CASCADE, null=True
                            ),
                        ),
                    ],
                    options={
                        "engine": models.ReplacingMergeTree(),
                        "cluster": "cluster",
                    },
                )
            )
            operations.append(
                migrations.CreateModel(
                    "RiderDistributed",
                    [
                        ("id", django_models.BigAutoField(primary_key=True)),
                        (
                            "pony",
                            django_models.ForeignKey(
                                "PonyDistributed", django_models.CASCADE
                            ),
                        ),
                        (
                            "friend",
                            django_models.ForeignKey(
                                "self", django_models.CASCADE, null=True
                            ),
                        ),
                    ],
                    options={
                        "engine": models.Distributed(
                            "cluster", models.currentDatabase(), f"{app_label}_rider"
                        ),
                        "cluster": "cluster",
                    },
                )
            )

        return self.apply_operations(app_label, ProjectState(), operations)

    def assertTableNotExistsCluster(self, table, dbs=("default", "s1r2", "s2r1")):
        for db in dbs:
            self.assertTableNotExists(table, db)

    def assertTableExistsCluster(self, table, dbs=("default", "s1r2", "s2r1")):
        for db in dbs:
            self.assertTableExists(table, db)
