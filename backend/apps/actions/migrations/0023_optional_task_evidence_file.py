from django.db import migrations, models

import common.storage


class Migration(migrations.Migration):
    dependencies = [
        ("actions", "0022_treatmentdeletionrecord"),
    ]

    operations = [
        migrations.AlterField(
            model_name="treatmenttaskevidence",
            name="file",
            field=models.FileField(blank=True, upload_to=common.storage.treatment_task_evidence_upload_to),
        ),
    ]
