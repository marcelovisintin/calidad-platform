from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0003_email_delivery_outbox"),
    ]

    operations = [
        migrations.AlterField(
            model_name="notification",
            name="task_type",
            field=models.CharField(
                blank=True,
                choices=[
                    ("", "Sin tarea"),
                    ("action_assignment", "Asignacion de accion"),
                    ("analysis_participation", "Participacion en analisis"),
                    ("finding_management", "Gestion de hallazgo"),
                    ("treatment_participation", "Participacion en tratamiento"),
                    ("verification_participation", "Participacion en verificacion"),
                ],
                default="",
                max_length=40,
            ),
        ),
    ]
