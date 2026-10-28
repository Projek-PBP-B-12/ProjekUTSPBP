from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("SharedPost", "0001_initial")]

    operations = [
        migrations.AlterField(
            model_name="sharedpost",
            name="location",
            field=models.ForeignKey(
                to="Location.location",
                on_delete=django.db.models.deletion.RESTRICT,
                related_name="shared_posts",
            ),
        ),
    ]
