from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0006_action_terminology"),
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
                    ("learned_lesson", "Leccion aprendida"),
                ],
                default="",
                max_length=40,
            ),
        ),
    ]
