from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid

import common.storage


class Migration(migrations.Migration):

    dependencies = [
        ("actions", "0008_treatmenttask_root_causes"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="TreatmentLearnedLesson",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("row_version", models.PositiveIntegerField(default=1)),
                ("has_learning", models.BooleanField(blank=True, null=True)),
                ("learned_text", models.TextField(blank=True)),
                ("no_learning_reason", models.TextField(blank=True)),
                ("procedure_modified", models.BooleanField(blank=True, null=True)),
                ("procedure_modification_notes", models.TextField(blank=True)),
                ("saved_at", models.DateTimeField(blank=True, null=True)),
                (
                    "created_by",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="%(class)s_created", to=settings.AUTH_USER_MODEL),
                ),
                (
                    "saved_by",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="treatment_learned_lessons_saved", to=settings.AUTH_USER_MODEL),
                ),
                (
                    "treatment",
                    models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="learned_lesson", to="actions.treatment"),
                ),
                (
                    "updated_by",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="%(class)s_updated", to=settings.AUTH_USER_MODEL),
                ),
            ],
            options={
                "verbose_name": "Leccion aprendida de tratamiento",
                "verbose_name_plural": "Lecciones aprendidas de tratamientos",
                "ordering": ("-updated_at",),
            },
        ),
        migrations.CreateModel(
            name="TreatmentLearnedLessonEvidence",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("row_version", models.PositiveIntegerField(default=1)),
                ("file", models.FileField(upload_to=common.storage.treatment_learned_lesson_evidence_upload_to)),
                ("original_name", models.CharField(max_length=255)),
                ("content_type", models.CharField(blank=True, max_length=100)),
                (
                    "created_by",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="%(class)s_created", to=settings.AUTH_USER_MODEL),
                ),
                (
                    "learned_lesson",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="evidences", to="actions.treatmentlearnedlesson"),
                ),
                (
                    "updated_by",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="%(class)s_updated", to=settings.AUTH_USER_MODEL),
                ),
                (
                    "uploaded_by",
                    models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="treatment_learned_lesson_evidences", to=settings.AUTH_USER_MODEL),
                ),
            ],
            options={
                "verbose_name": "Evidencia de leccion aprendida",
                "verbose_name_plural": "Evidencias de lecciones aprendidas",
                "ordering": ("-created_at",),
            },
        ),
    ]
