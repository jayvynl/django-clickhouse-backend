from django.db import OperationalError, connection, migrations
from django.db.migrations.state import ProjectState
from django.db.models import CheckConstraint, Q
from django.test import TestCase

from clickhouse_backend import compat, models

from .models import DistributedStudent, Student
from .test_base import OperationTestBase


class TestDistributed(TestCase):
    databases = {"default", "s1r2", "s2r1", "other"}

    def test_truncate_distributed_table(self):
        DistributedStudent.objects.bulk_create(
            [DistributedStudent(name=f"Student{i}", score=i * 10) for i in range(10)]
        )
        self._fixture_teardown()
        for db in ["default", "s1r2", "s2r1"]:
            for model in [Student, DistributedStudent]:
                self.assertFalse(model.objects.using(db).exists())

    def test_distributed_can_see_underlying_table(self):
        Student.objects.create(name="Jack", score=90)
        self.assertTrue(
            DistributedStudent.objects.filter(name="Jack", score=90).exists()
        )

    def test_write_distributed(self):
        students = DistributedStudent.objects.bulk_create(
            [DistributedStudent(name=f"Student{i}", score=i * 10) for i in range(10)]
        )
        self.assertEqual(DistributedStudent.objects.count(), 10)
        self.assertEqual(DistributedStudent.objects.using("s1r2").count(), 10)
        self.assertEqual(DistributedStudent.objects.using("s2r1").count(), 10)
        self.assertEqual(Student.objects.count(), Student.objects.using("s1r2").count())
        self.assertEqual(
            Student.objects.using("s1r2").count()
            + Student.objects.using("s2r1").count(),
            10,
        )
        DistributedStudent.objects.filter(id__in=[s.id for s in students[5:]]).update(
            name="lol"
        )
        self.assertEqual(DistributedStudent.objects.filter(name="lol").count(), 5)
        DistributedStudent.objects.filter(id__in=[s.id for s in students[:5]]).delete()
        self.assertEqual(DistributedStudent.objects.count(), 5)
        self.assertEqual(DistributedStudent.objects.using("s1r2").count(), 5)
        self.assertEqual(DistributedStudent.objects.using("s2r1").count(), 5)
        self.assertEqual(Student.objects.count(), Student.objects.using("s1r2").count())
        self.assertEqual(
            Student.objects.using("s1r2").count()
            + Student.objects.using("s2r1").count(),
            5,
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

    def test_add_field(self):
        """
        Tests the AddField operation.
        """
        # Test the state alteration
        operation = migrations.AddField(
            "Pony",
            "height",
            models.Float64Field(null=True, default=5),
        )
        self.assertEqual(operation.describe(), "Add field height to Pony")
        self.assertEqual(operation.migration_name_fragment, "pony_height")
        project_state, new_state = self.make_test_state("test_adfl", operation)
        self.assertEqual(len(new_state.models["test_adfl", "pony"].fields), 4)
        field = new_state.models["test_adfl", "pony"].fields["height"]
        self.assertEqual(field.default, 5)
        # Test the database alteration
        self.assertColumnNotExistsCluster("test_adfl_pony", "height")
        with connection.schema_editor() as editor:
            operation.database_forwards("test_adfl", editor, project_state, new_state)
        self.assertColumnExistsCluster("test_adfl_pony", "height")
        # And test reversal
        with connection.schema_editor() as editor:
            operation.database_backwards("test_adfl", editor, new_state, project_state)
        self.assertColumnNotExistsCluster("test_adfl_pony", "height")
        # And deconstruction
        definition = operation.deconstruct()
        self.assertEqual(definition[0], "AddField")
        self.assertEqual(definition[1], [])
        self.assertEqual(sorted(definition[2]), ["field", "model_name", "name"])

        # Test distributed table
        # Test the state alteration
        operation = migrations.AddField(
            "PonyDistributed",
            "height",
            models.Float64Field(null=True, default=5),
        )
        self.assertEqual(operation.describe(), "Add field height to PonyDistributed")
        self.assertEqual(operation.migration_name_fragment, "ponydistributed_height")
        new_state = project_state.clone()
        operation.state_forwards("test_adfl", new_state)
        self.assertEqual(
            len(new_state.models["test_adfl", "ponydistributed"].fields), 4
        )
        field = new_state.models["test_adfl", "ponydistributed"].fields["height"]
        self.assertEqual(field.default, 5)
        # Test the database alteration
        self.assertColumnNotExistsCluster("test_adfl_ponydistributed", "height")
        with connection.schema_editor() as editor:
            operation.database_forwards("test_adfl", editor, project_state, new_state)
        self.assertColumnExistsCluster("test_adfl_ponydistributed", "height")
        # And test reversal
        with connection.schema_editor() as editor:
            operation.database_backwards("test_adfl", editor, new_state, project_state)
        self.assertColumnNotExistsCluster("test_adfl_ponydistributed", "height")
        # And deconstruction
        definition = operation.deconstruct()
        self.assertEqual(definition[0], "AddField")
        self.assertEqual(definition[1], [])
        self.assertEqual(sorted(definition[2]), ["field", "model_name", "name"])

    def test_alter_field(self):
        """
        Tests the AlterField operation.
        """
        project_state = self.set_up_distributed_model("test_alfl")
        # Test the state alteration
        operation = migrations.AlterField("Pony", "pink", models.Int32Field(null=True))
        self.assertEqual(operation.describe(), "Alter field pink on Pony")
        self.assertEqual(operation.migration_name_fragment, "alter_pony_pink")
        new_state = project_state.clone()
        operation.state_forwards("test_alfl", new_state)
        self.assertIs(
            project_state.models["test_alfl", "pony"].fields["pink"].null, False
        )
        self.assertIs(new_state.models["test_alfl", "pony"].fields["pink"].null, True)
        # Test the database alteration
        self.assertColumnNotNullCluster("test_alfl_pony", "pink")
        with connection.schema_editor() as editor:
            operation.database_forwards("test_alfl", editor, project_state, new_state)
        self.assertColumnNullCluster("test_alfl_pony", "pink")
        # And test reversal
        with connection.schema_editor() as editor:
            operation.database_backwards("test_alfl", editor, new_state, project_state)
        self.assertColumnNotNullCluster("test_alfl_pony", "pink")
        # And deconstruction
        definition = operation.deconstruct()
        self.assertEqual(definition[0], "AlterField")
        self.assertEqual(definition[1], [])
        self.assertEqual(sorted(definition[2]), ["field", "model_name", "name"])

        # Test distributed table
        # Test the state alteration
        operation = migrations.AlterField(
            "PonyDistributed", "pink", models.Int32Field(null=True)
        )
        self.assertEqual(operation.describe(), "Alter field pink on PonyDistributed")
        self.assertEqual(
            operation.migration_name_fragment, "alter_ponydistributed_pink"
        )
        new_state = project_state.clone()
        operation.state_forwards("test_alfl", new_state)
        self.assertIs(
            project_state.models["test_alfl", "ponydistributed"].fields["pink"].null,
            False,
        )
        self.assertIs(
            new_state.models["test_alfl", "ponydistributed"].fields["pink"].null, True
        )
        # Test the database alteration
        self.assertColumnNotNullCluster("test_alfl_ponydistributed", "pink")
        with connection.schema_editor() as editor:
            operation.database_forwards("test_alfl", editor, project_state, new_state)
        self.assertColumnNullCluster("test_alfl_ponydistributed", "pink")
        # And test reversal
        with connection.schema_editor() as editor:
            operation.database_backwards("test_alfl", editor, new_state, project_state)
        self.assertColumnNotNullCluster("test_alfl_ponydistributed", "pink")
        # And deconstruction
        definition = operation.deconstruct()
        self.assertEqual(definition[0], "AlterField")
        self.assertEqual(definition[1], [])
        self.assertEqual(sorted(definition[2]), ["field", "model_name", "name"])

    def test_rename_field(self):
        """
        Tests the RenameField operation.
        """
        project_state = self.set_up_distributed_model("test_rnfl")
        operation = migrations.RenameField("Pony", "pink", "blue")
        self.assertEqual(operation.describe(), "Rename field pink on Pony to blue")
        self.assertEqual(operation.migration_name_fragment, "rename_pink_pony_blue")
        new_state = project_state.clone()
        operation.state_forwards("test_rnfl", new_state)
        self.assertIn("blue", new_state.models["test_rnfl", "pony"].fields)
        self.assertNotIn("pink", new_state.models["test_rnfl", "pony"].fields)
        # Rename field.
        self.assertColumnExistsCluster("test_rnfl_pony", "pink")
        self.assertColumnNotExistsCluster("test_rnfl_pony", "blue")
        with connection.schema_editor() as editor:
            operation.database_forwards("test_rnfl", editor, project_state, new_state)
        self.assertColumnExistsCluster("test_rnfl_pony", "blue")
        self.assertColumnNotExistsCluster("test_rnfl_pony", "pink")
        # Reversal.
        with connection.schema_editor() as editor:
            operation.database_backwards("test_rnfl", editor, new_state, project_state)
        self.assertColumnExistsCluster("test_rnfl_pony", "pink")
        self.assertColumnNotExistsCluster("test_rnfl_pony", "blue")
        # Deconstruction.
        definition = operation.deconstruct()
        self.assertEqual(definition[0], "RenameField")
        self.assertEqual(definition[1], [])
        self.assertEqual(
            definition[2],
            {"model_name": "Pony", "old_name": "pink", "new_name": "blue"},
        )

        # Test distributed table
        operation = migrations.RenameField("PonyDistributed", "pink", "blue")
        self.assertEqual(
            operation.describe(), "Rename field pink on PonyDistributed to blue"
        )
        self.assertEqual(
            operation.migration_name_fragment, "rename_pink_ponydistributed_blue"
        )
        new_state = project_state.clone()
        operation.state_forwards("test_rnfl", new_state)
        self.assertIn("blue", new_state.models["test_rnfl", "ponydistributed"].fields)
        self.assertNotIn(
            "pink", new_state.models["test_rnfl", "ponydistributed"].fields
        )
        # Rename field.
        self.assertColumnExistsCluster("test_rnfl_ponydistributed", "pink")
        self.assertColumnNotExistsCluster("test_rnfl_ponydistributed", "blue")
        with connection.schema_editor() as editor:
            operation.database_forwards("test_rnfl", editor, project_state, new_state)
        self.assertColumnExistsCluster("test_rnfl_ponydistributed", "blue")
        self.assertColumnNotExistsCluster("test_rnfl_ponydistributed", "pink")
        # Reversal.
        with connection.schema_editor() as editor:
            operation.database_backwards("test_rnfl", editor, new_state, project_state)
        self.assertColumnExistsCluster("test_rnfl_ponydistributed", "pink")
        self.assertColumnNotExistsCluster("test_rnfl_ponydistributed", "blue")
        # Deconstruction.
        definition = operation.deconstruct()
        self.assertEqual(definition[0], "RenameField")
        self.assertEqual(definition[1], [])
        self.assertEqual(
            definition[2],
            {"model_name": "PonyDistributed", "old_name": "pink", "new_name": "blue"},
        )

    def test_add_constraint(self):
        project_state = self.set_up_distributed_model("test_addconstraint")
        gt_check = Q(pink__gt=2)
        if compat.dj_ge51:
            gt_constraint = CheckConstraint(
                condition=gt_check, name="test_add_constraint_pony_pink_gt_2"
            )
        else:
            gt_constraint = CheckConstraint(
                check=gt_check, name="test_add_constraint_pony_pink_gt_2"
            )
        gt_operation = migrations.AddConstraint("Pony", gt_constraint)
        self.assertEqual(
            gt_operation.describe(),
            "Create constraint test_add_constraint_pony_pink_gt_2 on model Pony",
        )
        self.assertEqual(
            gt_operation.migration_name_fragment,
            "pony_test_add_constraint_pony_pink_gt_2",
        )
        # Test the state alteration
        new_state = project_state.clone()
        gt_operation.state_forwards("test_addconstraint", new_state)
        self.assertEqual(
            len(new_state.models["test_addconstraint", "pony"].options["constraints"]),
            1,
        )
        Pony = new_state.apps.get_model("test_addconstraint", "Pony")
        self.assertEqual(len(Pony._meta.constraints), 1)
        # Test the database alteration
        with connection.schema_editor() as editor:
            gt_operation.database_forwards(
                "test_addconstraint", editor, project_state, new_state
            )
        with self.assertRaises(OperationalError):
            Pony.objects.create(pink=1, weight=1.0)
        # Add another one.
        lt_check = Q(pink__lt=100)
        if compat.dj_ge51:
            lt_constraint = CheckConstraint(
                condition=lt_check, name="test_add_constraint_pony_pink_lt_100"
            )
        else:
            lt_constraint = CheckConstraint(
                check=lt_check, name="test_add_constraint_pony_pink_lt_100"
            )
        lt_operation = migrations.AddConstraint("Pony", lt_constraint)
        lt_operation.state_forwards("test_addconstraint", new_state)
        self.assertEqual(
            len(new_state.models["test_addconstraint", "pony"].options["constraints"]),
            2,
        )
        Pony = new_state.apps.get_model("test_addconstraint", "Pony")
        self.assertEqual(len(Pony._meta.constraints), 2)
        with connection.schema_editor() as editor:
            lt_operation.database_forwards(
                "test_addconstraint", editor, project_state, new_state
            )
        with self.assertRaises(OperationalError):
            Pony.objects.create(pink=100, weight=1.0)
        # Test reversal
        with connection.schema_editor() as editor:
            gt_operation.database_backwards(
                "test_addconstraint", editor, new_state, project_state
            )
        Pony.objects.create(pink=1, weight=1.0)
        # Test deconstruction
        definition = gt_operation.deconstruct()
        self.assertEqual(definition[0], "AddConstraint")
        self.assertEqual(definition[1], [])
        self.assertEqual(
            definition[2], {"model_name": "Pony", "constraint": gt_constraint}
        )

        # Test distributed table
        gt_check = Q(pink__gt=2)
        if compat.dj_ge51:
            gt_constraint = CheckConstraint(
                condition=gt_check, name="test_add_constraint_ponydistributed_pink_gt_2"
            )
        else:
            gt_constraint = CheckConstraint(
                check=gt_check, name="test_add_constraint_ponydistributed_pink_gt_2"
            )
        gt_operation = migrations.AddConstraint("PonyDistributed", gt_constraint)
        # Test the state alteration
        new_state = project_state.clone()
        gt_operation.state_forwards("test_addconstraint", new_state)
        # Test the database alteration
        with connection.schema_editor() as editor:
            with self.assertRaises(TypeError):
                gt_operation.database_forwards(
                    "test_addconstraint", editor, project_state, new_state
                )

    def test_remove_constraint(self):
        if compat.dj_ge51:
            constraints = [
                CheckConstraint(
                    condition=Q(pink__gt=2),
                    name="test_remove_constraint_pony_pink_gt_2",
                ),
                CheckConstraint(
                    condition=Q(pink__lt=100),
                    name="test_remove_constraint_pony_pink_lt_100",
                ),
            ]
        else:
            constraints = (
                [
                    CheckConstraint(
                        check=Q(pink__gt=2),
                        name="test_remove_constraint_pony_pink_gt_2",
                    ),
                    CheckConstraint(
                        check=Q(pink__lt=100),
                        name="test_remove_constraint_pony_pink_lt_100",
                    ),
                ],
            )
        project_state = self.set_up_distributed_model(
            "test_removeconstraint",
            constraints=constraints,
        )
        gt_operation = migrations.RemoveConstraint(
            "Pony", "test_remove_constraint_pony_pink_gt_2"
        )
        self.assertEqual(
            gt_operation.describe(),
            "Remove constraint test_remove_constraint_pony_pink_gt_2 from model Pony",
        )
        self.assertEqual(
            gt_operation.migration_name_fragment,
            "remove_pony_test_remove_constraint_pony_pink_gt_2",
        )
        # Test state alteration
        new_state = project_state.clone()
        gt_operation.state_forwards("test_removeconstraint", new_state)
        self.assertEqual(
            len(
                new_state.models["test_removeconstraint", "pony"].options["constraints"]
            ),
            1,
        )
        Pony = new_state.apps.get_model("test_removeconstraint", "Pony")
        self.assertEqual(len(Pony._meta.constraints), 1)
        # Test database alteration
        with connection.schema_editor() as editor:
            gt_operation.database_forwards(
                "test_removeconstraint", editor, project_state, new_state
            )
        Pony.objects.create(pink=1, weight=1.0).delete()
        with self.assertRaises(OperationalError):
            Pony.objects.create(pink=100, weight=1.0)
        # Remove the other one.
        lt_operation = migrations.RemoveConstraint(
            "Pony", "test_remove_constraint_pony_pink_lt_100"
        )
        lt_operation.state_forwards("test_removeconstraint", new_state)
        self.assertEqual(
            len(
                new_state.models["test_removeconstraint", "pony"].options["constraints"]
            ),
            0,
        )
        Pony = new_state.apps.get_model("test_removeconstraint", "Pony")
        self.assertEqual(len(Pony._meta.constraints), 0)
        with connection.schema_editor() as editor:
            lt_operation.database_forwards(
                "test_removeconstraint", editor, project_state, new_state
            )
        Pony.objects.create(pink=100, weight=1.0).delete()
        # Test reversal
        with connection.schema_editor() as editor:
            gt_operation.database_backwards(
                "test_removeconstraint", editor, new_state, project_state
            )
        with self.assertRaises(OperationalError):
            Pony.objects.create(pink=1, weight=1.0)
        # Test deconstruction
        definition = gt_operation.deconstruct()
        self.assertEqual(definition[0], "RemoveConstraint")
        self.assertEqual(definition[1], [])
        self.assertEqual(
            definition[2],
            {"model_name": "Pony", "name": "test_remove_constraint_pony_pink_gt_2"},
        )

    def test_add_index(self):
        """
        Test the AddIndex operation.
        """
        project_state = self.set_up_distributed_model("test_adin")
        index = models.Index(
            fields=["pink"],
            name="test_adin_pony_pink_idx",
            type=models.Set(1000),
            granularity=4,
        )
        operation = migrations.AddIndex("Pony", index)
        self.assertEqual(
            operation.describe(),
            "Create index test_adin_pony_pink_idx on field(s) pink of model Pony",
        )
        self.assertEqual(
            operation.migration_name_fragment,
            "pony_test_adin_pony_pink_idx",
        )
        new_state = project_state.clone()
        operation.state_forwards("test_adin", new_state)
        # Test the database alteration
        self.assertEqual(
            len(new_state.models["test_adin", "pony"].options["indexes"]), 1
        )
        self.assertIndexNameNotExistsCluster("test_adin_pony", "pony_pink_idx")
        with connection.schema_editor() as editor:
            operation.database_forwards("test_adin", editor, project_state, new_state)
        self.assertIndexNameExistsCluster("test_adin_pony", "test_adin_pony_pink_idx")
        # And test reversal
        with connection.schema_editor() as editor:
            operation.database_backwards("test_adin", editor, new_state, project_state)
        self.assertIndexNameNotExistsCluster(
            "test_adin_pony", "test_adin_pony_pink_idx"
        )
        # And deconstruction
        definition = operation.deconstruct()
        self.assertEqual(definition[0], "AddIndex")
        self.assertEqual(definition[1], [])
        self.assertEqual(definition[2], {"model_name": "Pony", "index": index})

        # Test distributed table
        operation = migrations.AddIndex("PonyDistributed", index)
        new_state = project_state.clone()
        operation.state_forwards("test_adin", new_state)
        with connection.schema_editor() as editor:
            with self.assertRaises(TypeError):
                operation.database_forwards(
                    "test_adin", editor, project_state, new_state
                )

    def test_remove_index(self):
        """
        Test the RemoveIndex operation.
        """
        project_state = self.set_up_distributed_model("test_rmin", multicol_index=True)
        self.assertIndexNameExistsCluster("test_rmin_pony", "pony_test_idx")
        operation = migrations.RemoveIndex("Pony", "pony_test_idx")
        self.assertEqual(operation.describe(), "Remove index pony_test_idx from Pony")
        self.assertEqual(
            operation.migration_name_fragment,
            "remove_pony_pony_test_idx",
        )
        new_state = project_state.clone()
        operation.state_forwards("test_rmin", new_state)
        # Test the state alteration
        self.assertEqual(
            len(new_state.models["test_rmin", "pony"].options["indexes"]), 0
        )
        self.assertIndexNameExistsCluster("test_rmin_pony", "pony_test_idx")
        # Test the database alteration
        with connection.schema_editor() as editor:
            operation.database_forwards("test_rmin", editor, project_state, new_state)
        self.assertIndexNameNotExistsCluster("test_rmin_pony", "pink_weight_idx")
        # And test reversal
        with connection.schema_editor() as editor:
            operation.database_backwards("test_rmin", editor, new_state, project_state)
        self.assertIndexNameExistsCluster("test_rmin_pony", "pony_test_idx")
        # And deconstruction
        definition = operation.deconstruct()
        self.assertEqual(definition[0], "RemoveIndex")
        self.assertEqual(definition[1], [])
        self.assertEqual(definition[2], {"model_name": "Pony", "name": "pony_test_idx"})

        # Also test a field dropped with index - sqlite remake issue
        operations = [
            migrations.RemoveIndex("Pony", "pony_test_idx"),
            migrations.RemoveField("Pony", "pink"),
        ]
        self.assertColumnExistsCluster("test_rmin_pony", "pink")
        self.assertIndexNameExistsCluster("test_rmin_pony", "pony_test_idx")
        # Test database alteration
        new_state = project_state.clone()
        self.apply_operations("test_rmin", new_state, operations=operations)
        self.assertColumnNotExistsCluster("test_rmin_pony", "pink")
        self.assertIndexNameNotExistsCluster("test_rmin_pony", "pony_test_idx")
        # And test reversal
        self.unapply_operations("test_rmin", project_state, operations=operations)
        self.assertIndexNameExistsCluster("test_rmin_pony", "pony_test_idx")

    if compat.dj_ge41:

        def test_rename_index(self):
            app_label = "test_rnin"
            project_state = self.set_up_distributed_model(app_label, index=True)
            table_name = app_label + "_pony"
            self.assertIndexNameExistsCluster(table_name, "pony_pink_idx")
            self.assertIndexNameNotExistsCluster(table_name, "new_pony_test_idx")
            operation = migrations.RenameIndex(
                "Pony", new_name="new_pony_test_idx", old_name="pony_pink_idx"
            )
            self.assertEqual(
                operation.describe(),
                "Rename index pony_pink_idx on Pony to new_pony_test_idx",
            )
            self.assertEqual(
                operation.migration_name_fragment,
                "rename_pony_pink_idx_new_pony_test_idx",
            )

            new_state = project_state.clone()
            operation.state_forwards(app_label, new_state)
            # Rename index.
            expected_queries = 1 if connection.features.can_rename_index else 2
            with connection.schema_editor() as editor, self.assertNumQueries(
                expected_queries
            ):
                operation.database_forwards(app_label, editor, project_state, new_state)
            self.assertIndexNameNotExistsCluster(table_name, "pony_pink_idx")
            self.assertIndexNameExistsCluster(table_name, "new_pony_test_idx")
            # Reversal.
            with connection.schema_editor() as editor, self.assertNumQueries(
                expected_queries
            ):
                operation.database_backwards(
                    app_label, editor, new_state, project_state
                )
            self.assertIndexNameExistsCluster(table_name, "pony_pink_idx")
            self.assertIndexNameNotExistsCluster(table_name, "new_pony_test_idx")
            # Deconstruction.
            definition = operation.deconstruct()
            self.assertEqual(definition[0], "RenameIndex")
            self.assertEqual(definition[1], [])
            self.assertEqual(
                definition[2],
                {
                    "model_name": "Pony",
                    "old_name": "pony_pink_idx",
                    "new_name": "new_pony_test_idx",
                },
            )
