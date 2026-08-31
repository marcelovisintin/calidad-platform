import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.utils import timezone


class Migration(migrations.Migration):
    dependencies = [
        ("actions", "0014_treatmenttask_completed_at"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="TreatmentLearnedLessonRevision",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("row_version", models.PositiveIntegerField(default=1)),
                ("revision_number", models.PositiveIntegerField()),
                ("has_learning", models.BooleanField(blank=True, null=True)),
                ("learned_text", models.TextField(blank=True)),
                ("no_learning_reason", models.TextField(blank=True)),
                ("procedure_modified", models.BooleanField(blank=True, null=True)),
                ("procedure_modification_notes", models.TextField(blank=True)),
                ("changed_fields", models.JSONField(blank=True, default=list)),
                ("changed_at", models.DateTimeField(default=timezone.now)),
                ("changed_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="treatment_learned_lesson_revisions", to=settings.AUTH_USER_MODEL)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="%(class)s_created", to=settings.AUTH_USER_MODEL)),
                ("evidences", models.ManyToManyField(blank=True, related_name="lesson_revisions", to="actions.treatmentlearnedlessonevidence")),
                ("learned_lesson", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="revisions", to="actions.treatmentlearnedlesson")),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="%(class)s_updated", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Revision de leccion aprendida",
                "verbose_name_plural": "Revisiones de lecciones aprendidas",
                "ordering": ("-revision_number",),
            },
        ),
        migrations.AddConstraint(
            model_name="treatmentlearnedlessonrevision",
            constraint=models.UniqueConstraint(fields=("learned_lesson", "revision_number"), name="unique_treatment_lesson_revision"),
        ),
    ]
