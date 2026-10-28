from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("Location", "0002_location_owner_alter_location_latitude_and_more"),
    ]

    operations = [
        migrations.AlterModelOptions(name="location", options={"ordering": ["area_name", "pk"]}),
        migrations.AddConstraint(
            model_name="location",
            constraint=models.CheckConstraint(
                condition=models.Q(latitude__gte=-90, latitude__lte=90),
                name="location_latitude_range",
            ),
        ),
        migrations.AddConstraint(
            model_name="location",
            constraint=models.CheckConstraint(
                condition=models.Q(longitude__gte=-180, longitude__lte=180),
                name="location_longitude_range",
            ),
        ),
    ]
