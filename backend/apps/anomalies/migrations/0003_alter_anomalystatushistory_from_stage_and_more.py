from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("anomalies", "0002_workflow_core"),
    ]

    operations = [
        migrations.AlterField(
            model_name="anomalystatushistory",
            name="from_stage",
            field=models.CharField(
                choices=[
                    ("registration", "Registro"),
                    ("containment", "Contencion"),
                    ("initial_verification", "Verificacion inicial"),
                    ("classification", "REVICION DE HALLAZGOS"),
                    ("cause_analysis", "Analisis de causa"),
                    ("proposals", "Propuestas"),
                    ("action_plan", "Plan de accion"),
                    ("execution_follow_up", "Ejecucion y seguimiento"),
                    ("results", "Resultados"),
                    ("effectiveness_verification", "Verificacion de eficacia"),
                    ("closure", "Cierre"),
                    ("standardization_learning", "Estandarizacion y aprendizaje"),
                ],
                max_length=40,
            ),
        ),
        migrations.AlterField(
            model_name="anomalystatushistory",
            name="to_stage",
            field=models.CharField(
                choices=[
                    ("registration", "Registro"),
                    ("containment", "Contencion"),
                    ("initial_verification", "Verificacion inicial"),
                    ("classification", "REVICION DE HALLAZGOS"),
                    ("cause_analysis", "Analisis de causa"),
                    ("proposals", "Propuestas"),
                    ("action_plan", "Plan de accion"),
                    ("execution_follow_up", "Ejecucion y seguimiento"),
                    ("results", "Resultados"),
                    ("effectiveness_verification", "Verificacion de eficacia"),
                    ("closure", "Cierre"),
                    ("standardization_learning", "Estandarizacion y aprendizaje"),
                ],
                max_length=40,
            ),
        ),
    ]
