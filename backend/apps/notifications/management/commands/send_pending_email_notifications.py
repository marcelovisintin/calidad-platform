from django.conf import settings
from django.core.management.base import BaseCommand

from apps.notifications.services.email_delivery import dispatch_pending_email_notifications


class Command(BaseCommand):
    help = "Envia las notificaciones de correo pendientes y reintenta fallos transitorios."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)

    def handle(self, *args, **options):
        if not settings.EMAIL_NOTIFICATIONS_ENABLED:
            self.stdout.write(self.style.WARNING("Envio de correos desactivado por configuracion."))
            return

        result = dispatch_pending_email_notifications(limit=options["limit"])
        self.stdout.write(
            self.style.SUCCESS(
                "Correos procesados: "
                f"{result['claimed']}; enviados: {result['delivered']}; "
                f"fallidos: {result['failed']}; omitidos: {result['skipped']}."
            )
        )
