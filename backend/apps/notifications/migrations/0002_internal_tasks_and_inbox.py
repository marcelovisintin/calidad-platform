from django.db import migrations, models


CATEGORY_BY_SOURCE_PREFIX = {
    "anomalies.": "anomaly",
    "actions.": "action",
}


def forwards_populate_notification_metadata(apps, schema_editor):
    Notification = apps.get_model("notifications", "Notification")
    NotificationRecipient = apps.get_model("notifications", "NotificationRecipient")
    db_alias = schema_editor.connection.alias

    for notification in Notification.objects.using(db_alias).all():
        updates = {}
        if not notification.title:
            source_type = notification.source_type or ""
            template_code = notification.template_code or ""
            if template_code:
                title = template_code.replace("_", " ").strip().title()
            elif source_type.startswith("anomalies."):
                title = "Notificacion de anomalia"
            elif source_type.startswith("actions."):
                title = "Notificacion de accion"
            else:
                title = "Notificacion interna"
            updates["title"] = title
        if notification.body is None:
            updates["body"] = ""
        if notification.action_url is None:
            updates["action_url"] = ""
        if not notification.category:
            category = "info"
            for prefix, category_value in CATEGORY_BY_SOURCE_PREFIX.items():
                if (notification.source_type or "").startswith(prefix):
                    category = category_value
                    break
            updates["category"] = category
        if notification.template_code is None:
            updates["template_code"] = ""
        if updates:
            Notification.objects.using(db_alias).filter(pk=notification.pk).update(**updates)

    NotificationRecipient.objects.using(db_alias).filter(task_status__isnull=True).update(task_status="none")


def noop_reverse(apps, schema_editor):
    return None


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="notification",
            name="title",
            field=models.CharField(default="Notificacion interna", max_length=255),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="notification",
            name="body",
            field=models.TextField(blank=True, default=""),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="notification",
            name="category",
            field=models.CharField(choices=[("info", "Informacion"), ("action", "Accion"), ("participation", "Participacion"), ("anomaly", "Anomalia"), ("system", "Sistema")], default="info", max_length=30),
        ),
        migrations.AddField(
            model_name="notification",
            name="is_task",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="notification",
            name="task_type",
            field=models.CharField(blank=True, choices=[("", "Sin tarea"), ("action_assignment", "Asignacion de accion"), ("analysis_participation", "Participacion en analisis"), ("treatment_participation", "Participacion en tratamiento"), ("verification_participation", "Participacion en verificacion")], default="", max_length=40),
        ),
        migrations.AddField(
            model_name="notification",
            name="action_url",
            field=models.CharField(blank=True, default="", max_length=255),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="notification",
            name="due_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="notification",
            name="template_code",
            field=models.CharField(blank=True, default="", max_length=50),
        ),
        migrations.AddIndex(
            model_name="notification",
            index=models.Index(fields=["source_type", "source_id"], name="noti_source_idx"),
        ),
        migrations.AddField(
            model_name="notificationrecipient",
            name="task_status",
            field=models.CharField(choices=[("none", "Sin tarea"), ("pending", "Pendiente"), ("in_progress", "En curso"), ("completed", "Completada"), ("dismissed", "Descartada")], default="none", max_length=20),
        ),
        migrations.AddField(
            model_name="notificationrecipient",
            name="assigned_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="notificationrecipient",
            name="resolved_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddIndex(
            model_name="notificationrecipient",
            index=models.Index(fields=["user", "task_status", "resolved_at"], name="notifications_user_task_idx"),
        ),
        migrations.RunPython(forwards_populate_notification_metadata, noop_reverse),
    ]
