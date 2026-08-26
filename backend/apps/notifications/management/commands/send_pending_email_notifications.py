from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.notifications.services.digest_service import create_due_notification_digests
from apps.notifications.services.email_delivery import dispatch_pending_email_notifications


class Command(BaseCommand):
    help = "Envia las notificaciones de correo pendientes y reintenta fallos transitorios."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)

    def handle(self, *args, **options):
        if not settings.EMAIL_NOTIFICATIONS_ENABLED:
            self.stdout.write(self.style.WARNING("Envio de correos desactivado por configuracion."))
            return

        digest_result = {"created": 0}
        if timezone.localtime().hour >= settings.EMAIL_DUE_DIGEST_HOUR:
            digest_result = create_due_notification_digests()
        result = dispatch_pending_email_notifications(limit=options["limit"])
        self.stdout.write(
            self.style.SUCCESS(
                "Correos procesados: "
                f"{result['claimed']}; enviados: {result['delivered']}; "
                f"fallidos: {result['failed']}; omitidos: {result['skipped']}; "
                f"resumenes diarios creados: {digest_result['created']}."
            )
        )
