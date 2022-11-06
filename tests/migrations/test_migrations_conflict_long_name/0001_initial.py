from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    operations = [
        migrations.CreateModel(
            "Author",
            [
                ("id", models.BigAutoField(primary_key=True)),
            ],
        ),
    ]
