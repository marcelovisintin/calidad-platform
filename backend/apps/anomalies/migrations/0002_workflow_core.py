import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


OLD_TO_NEW_STATUS = {
    "draft": "registered",
    "reported": "registered",
    "under_review": "in_evaluation",
    "action_plan_pending": "in_treatment",
    "in_progress": "in_treatment",
    "pending_verification": "pending_verification",
    "closed": "closed",
    "cancelled": "cancelled",
}

OLD_TO_STAGE = {
    "draft": "registration",
    "reported": "registration",
    "under_review": "initial_verification",
    "action_plan_pending": "action_plan",
    "in_progress": "execution_follow_up",
    "pending_verification": "effectiveness_verification",
    "closed": "closure",
    "cancelled": "registration",
}



def migrate_existing_workflow(apps, schema_editor):
    Anomaly = apps.get_model("anomalies", "Anomaly")
    AnomalyStatusHistory = apps.get_model("anomalies", "AnomalyStatusHistory")

    for anomaly in Anomaly.objects.all():
        old_status = anomaly.current_status
        anomaly.current_status = OLD_TO_NEW_STATUS.get(old_status, "registered")
        anomaly.current_stage = OLD_TO_STAGE.get(old_status, "registration")
        if not anomaly.last_transition_at:
            anomaly.last_transition_at = anomaly.closed_at or anomaly.updated_at
        anomaly.save(update_fields=["current_status", "current_stage", "last_transition_at"])

    for history in AnomalyStatusHistory.objects.all():
        old_from = history.from_status
        old_to = history.to_status
        history.from_status = OLD_TO_NEW_STATUS.get(old_from, "registered")
        history.to_status = OLD_TO_NEW_STATUS.get(old_to, "registered")
        history.from_stage = OLD_TO_STAGE.get(old_from, "registration")
        history.to_stage = OLD_TO_STAGE.get(old_to, "registration")
        history.comment = history.reason or "Transicion registrada."
        history.save(update_fields=["from_status", "to_status", "from_stage", "to_stage", "comment"])



def reverse_workflow_migration(apps, schema_editor):
    Anomaly = apps.get_model("anomalies", "Anomaly")
    AnomalyStatusHistory = apps.get_model("anomalies", "AnomalyStatusHistory")
    new_to_old_status = {
        "registered": "reported",
        "in_evaluation": "under_review",
        "in_analysis": "under_review",
        "in_treatment": "in_progress",
        "pending_verification": "pending_verification",
        "closed": "closed",
        "cancelled": "cancelled",
        "reopened": "in_progress",
    }

    for anomaly in Anomaly.objects.all():
        anomaly.current_status = new_to_old_status.get(anomaly.current_status, "reported")
        anomaly.save(update_fields=["current_status"])

    for history in AnomalyStatusHistory.objects.all():
        history.from_status = new_to_old_status.get(history.from_status, "reported")
        history.to_status = new_to_old_status.get(history.to_status, "reported")
        history.reason = history.comment
        history.save(update_fields=["from_status", "to_status", "reason"])


class Migration(migrations.Migration):

    dependencies = [
        ("anomalies", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="anomaly",
            name="affected_process",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="anomaly",
            name="cancellation_reason",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="anomaly",
            name="classification_summary",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="anomaly",
            name="closure_comment",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="anomaly",
            name="containment_summary",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="anomaly",
            name="current_stage",
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
                default="registration",
                max_length=40,
            ),
        ),
        migrations.AddField(
            model_name="anomaly",
            name="effectiveness_summary",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="anomaly",
            name="last_transition_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="anomaly",
            name="result_summary",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="anomaly",
            name="reopened_count",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AlterField(
            model_name="anomaly",
            name="current_status",
            field=models.CharField(
                choices=[
                    ("registered", "Registrada"),
                    ("in_evaluation", "En evaluacion"),
                    ("in_analysis", "En analisis"),
                    ("in_treatment", "En tratamiento"),
                    ("pending_verification", "Pendiente de verificacion"),
                    ("closed", "Cerrada"),
                    ("cancelled", "Anulada"),
                    ("reopened", "Reabierta"),
                ],
                default="registered",
                max_length=40,
            ),
        ),
        migrations.AddField(
            model_name="anomalycomment",
            name="comment_type",
            field=models.CharField(
                choices=[
                    ("general", "General"),
                    ("containment", "Contencion"),
                    ("analysis", "Analisis"),
                    ("result", "Resultado"),
                    ("closure", "Cierre"),
                ],
                default="general",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="anomalystatushistory",
            name="comment",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
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
                default="registration",
                max_length=40,
            ),
        ),
        migrations.AddField(
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
                default="registration",
                max_length=40,
            ),
        ),
        migrations.RunPython(migrate_existing_workflow, reverse_workflow_migration),
        migrations.RemoveField(
            model_name="anomalystatushistory",
            name="reason",
        ),
        migrations.AlterField(
            model_name="anomalystatushistory",
            name="comment",
            field=models.TextField(),
        ),
        migrations.AlterField(
            model_name="anomalystatushistory",
            name="from_status",
            field=models.CharField(
                choices=[
                    ("registered", "Registrada"),
                    ("in_evaluation", "En evaluacion"),
                    ("in_analysis", "En analisis"),
                    ("in_treatment", "En tratamiento"),
                    ("pending_verification", "Pendiente de verificacion"),
                    ("closed", "Cerrada"),
                    ("cancelled", "Anulada"),
                    ("reopened", "Reabierta"),
                ],
                max_length=40,
            ),
        ),
        migrations.AlterField(
            model_name="anomalystatushistory",
            name="to_status",
            field=models.CharField(
                choices=[
                    ("registered", "Registrada"),
                    ("in_evaluation", "En evaluacion"),
                    ("in_analysis", "En analisis"),
                    ("in_treatment", "En tratamiento"),
                    ("pending_verification", "Pendiente de verificacion"),
                    ("closed", "Cerrada"),
                    ("cancelled", "Anulada"),
                    ("reopened", "Reabierta"),
                ],
                max_length=40,
            ),
        ),
        migrations.AlterModelOptions(
            name="anomalystatushistory",
            options={
                "ordering": ("-changed_at", "-created_at"),
                "verbose_name": "Historial de estado",
                "verbose_name_plural": "Historial de estados",
            },
        ),
        migrations.CreateModel(
            name="AnomalyCauseAnalysis",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("row_version", models.PositiveIntegerField(default=1)),
                ("analyzed_at", models.DateTimeField()),
                ("method_used", models.CharField(choices=[("five_whys", "5 Why"), ("ishikawa", "Ishikawa"), ("a3", "A3"), ("8d", "8D"), ("pdca", "PDCA"), ("other", "Otro")], max_length=30)),
                ("immediate_cause", models.TextField(blank=True)),
                ("root_cause", models.TextField(blank=True)),
                ("summary", models.TextField(blank=True)),
                ("analyzed_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="anomaly_cause_analyses", to=settings.AUTH_USER_MODEL)),
                ("anomaly", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="cause_analysis", to="anomalies.anomaly")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="%(class)s_created", to=settings.AUTH_USER_MODEL)),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="%(class)s_updated", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Analisis de causa",
                "verbose_name_plural": "Analisis de causa",
            },
        ),
        migrations.CreateModel(
            name="AnomalyClassification",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("row_version", models.PositiveIntegerField(default=1)),
                ("classified_at", models.DateTimeField()),
                ("containment_required", models.BooleanField(default=True)),
                ("requires_action_plan", models.BooleanField(default=True)),
                ("requires_effectiveness_verification", models.BooleanField(default=True)),
                ("impact_scope", models.CharField(blank=True, max_length=255)),
                ("summary", models.TextField(blank=True)),
                ("anomaly", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="classification", to="anomalies.anomaly")),
                ("classified_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="anomaly_classifications", to=settings.AUTH_USER_MODEL)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="%(class)s_created", to=settings.AUTH_USER_MODEL)),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="%(class)s_updated", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "REVICION DE HALLAZGOS de anomalia",
                "verbose_name_plural": "REVICION DE HALLAZGOS de anomalia",
            },
        ),
        migrations.CreateModel(
            name="AnomalyEffectivenessCheck",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("row_version", models.PositiveIntegerField(default=1)),
                ("verified_at", models.DateTimeField()),
                ("is_effective", models.BooleanField()),
                ("evidence_summary", models.TextField(blank=True)),
                ("comment", models.TextField()),
                ("recommended_stage", models.CharField(blank=True, choices=[("registration", "Registro"), ("containment", "Contencion"), ("initial_verification", "Verificacion inicial"), ("classification", "REVICION DE HALLAZGOS"), ("cause_analysis", "Analisis de causa"), ("proposals", "Propuestas"), ("action_plan", "Plan de accion"), ("execution_follow_up", "Ejecucion y seguimiento"), ("results", "Resultados"), ("effectiveness_verification", "Verificacion de eficacia"), ("closure", "Cierre"), ("standardization_learning", "Estandarizacion y aprendizaje")], max_length=40)),
                ("anomaly", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="effectiveness_checks", to="anomalies.anomaly")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="%(class)s_created", to=settings.AUTH_USER_MODEL)),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="%(class)s_updated", to=settings.AUTH_USER_MODEL)),
                ("verified_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="anomaly_effectiveness_checks", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ("-verified_at", "-created_at"),
                "verbose_name": "Verificacion de eficacia",
                "verbose_name_plural": "Verificaciones de eficacia",
            },
        ),
        migrations.CreateModel(
            name="AnomalyInitialVerification",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("row_version", models.PositiveIntegerField(default=1)),
                ("verified_at", models.DateTimeField()),
                ("material_checked", models.BooleanField(default=False)),
                ("machine_checked", models.BooleanField(default=False)),
                ("method_checked", models.BooleanField(default=False)),
                ("manpower_checked", models.BooleanField(default=False)),
                ("milieu_checked", models.BooleanField(default=False)),
                ("measurement_checked", models.BooleanField(default=False)),
                ("material_notes", models.TextField(blank=True)),
                ("machine_notes", models.TextField(blank=True)),
                ("method_notes", models.TextField(blank=True)),
                ("manpower_notes", models.TextField(blank=True)),
                ("milieu_notes", models.TextField(blank=True)),
                ("measurement_notes", models.TextField(blank=True)),
                ("summary", models.TextField(blank=True)),
                ("anomaly", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="initial_verification", to="anomalies.anomaly")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="%(class)s_created", to=settings.AUTH_USER_MODEL)),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="%(class)s_updated", to=settings.AUTH_USER_MODEL)),
                ("verified_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="initial_verifications", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Verificacion inicial",
                "verbose_name_plural": "Verificaciones iniciales",
            },
        ),
        migrations.CreateModel(
            name="AnomalyLearning",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("row_version", models.PositiveIntegerField(default=1)),
                ("recorded_at", models.DateTimeField()),
                ("standardization_actions", models.TextField(blank=True)),
                ("lessons_learned", models.TextField(blank=True)),
                ("document_changes", models.TextField(blank=True)),
                ("shared_with", models.TextField(blank=True)),
                ("shared_at", models.DateTimeField(blank=True, null=True)),
                ("anomaly", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="learning", to="anomalies.anomaly")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="%(class)s_created", to=settings.AUTH_USER_MODEL)),
                ("recorded_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="anomaly_learning_records", to=settings.AUTH_USER_MODEL)),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="%(class)s_updated", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Estandarizacion y aprendizaje",
                "verbose_name_plural": "Estandarizacion y aprendizaje",
            },
        ),
        migrations.CreateModel(
            name="AnomalyParticipant",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("row_version", models.PositiveIntegerField(default=1)),
                ("role", models.CharField(choices=[("reporter", "Registrador"), ("owner", "Responsable"), ("reviewer", "Evaluador"), ("analyst", "Analista"), ("implementer", "Implementador"), ("verifier", "Verificador"), ("observer", "Observador")], max_length=30)),
                ("note", models.TextField(blank=True)),
                ("anomaly", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="participants", to="anomalies.anomaly")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="%(class)s_created", to=settings.AUTH_USER_MODEL)),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="%(class)s_updated", to=settings.AUTH_USER_MODEL)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="anomaly_participations", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ("role", "created_at"),
                "verbose_name": "Participante de anomalia",
                "verbose_name_plural": "Participantes de anomalia",
            },
        ),
        migrations.CreateModel(
            name="AnomalyProposal",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("row_version", models.PositiveIntegerField(default=1)),
                ("title", models.CharField(max_length=255)),
                ("description", models.TextField()),
                ("proposed_at", models.DateTimeField()),
                ("is_selected", models.BooleanField(default=False)),
                ("sequence", models.PositiveIntegerField(default=1)),
                ("anomaly", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="proposals", to="anomalies.anomaly")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="%(class)s_created", to=settings.AUTH_USER_MODEL)),
                ("proposed_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="anomaly_proposals", to=settings.AUTH_USER_MODEL)),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="%(class)s_updated", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ("sequence", "created_at"),
                "verbose_name": "Propuesta",
                "verbose_name_plural": "Propuestas",
            },
        ),
        migrations.AddConstraint(
            model_name="anomalyparticipant",
            constraint=models.UniqueConstraint(fields=("anomaly", "user", "role"), name="anom_part_usr_role_uq"),
        ),
        migrations.AddConstraint(
            model_name="anomalyproposal",
            constraint=models.UniqueConstraint(fields=("anomaly", "sequence"), name="anom_prop_seq_uq"),
        ),
        migrations.RemoveIndex(
            model_name="anomaly",
            name="anom_status_prio_area_idx",
        ),
        migrations.AddIndex(
            model_name="anomaly",
            index=models.Index(fields=["current_status", "current_stage", "area"], name="anom_stat_stage_area_idx"),
        ),
    ]

