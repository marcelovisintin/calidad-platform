import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("actions", "0018_action_terminology"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="treatment", name="formally_closed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="treatmentlearnedlesson", name="status",
            field=models.CharField(
                choices=[("draft", "Borrador"), ("ready", "Lista para publicar"),
                         ("published", "Publicada")],
                default="draft", max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="treatmentlearnedlesson", name="published_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="treatmentlearnedlesson", name="published_by",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name="published_treatment_lessons", to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="treatmenttask", name="derived_from_lesson",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name="derived_actions", to="actions.treatmentlearnedlesson",
            ),
        ),
    ]
