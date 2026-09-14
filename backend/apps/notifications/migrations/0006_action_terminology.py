from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0005_notificationrecipient_email_content"),
    ]

    operations = [
        migrations.AlterField(
            model_name="notification",
            name="task_type",
            field=models.CharField(
                blank=True,
                choices=[
                    ("", "Sin accion"),
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
        migrations.AlterField(
            model_name="notificationrecipient",
            name="task_status",
            field=models.CharField(
                choices=[
                    ("none", "Sin accion"),
                    ("pending", "Pendiente"),
                    ("in_progress", "En curso"),
                    ("completed", "Completada"),
                    ("dismissed", "Descartada"),
                ],
                default="none",
                max_length=20,
            ),
        ),
    ]
