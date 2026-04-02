from django.core.management.base import BaseCommand

from apps.accounts.models import User


class Command(BaseCommand):
    help = "Marca usuarios para cambio obligatorio de contraseña en el próximo login."

    def add_arguments(self, parser):
        parser.add_argument(
            "--active-only",
            action="store_true",
            help="Aplicar solo a usuarios activos.",
        )
        parser.add_argument(
            "--exclude-superusers",
            action="store_true",
            help="Excluir superusuarios.",
        )
        parser.add_argument(
            "--username",
            action="append",
            dest="usernames",
            help="Filtrar por username (puede repetirse).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Solo muestra cuántos usuarios serían afectados.",
        )

    def handle(self, *args, **options):
        queryset = User.objects.all()

        if options["active_only"]:
            queryset = queryset.filter(is_active=True)

        if options["exclude_superusers"]:
            queryset = queryset.filter(is_superuser=False)

        usernames = options.get("usernames")
        if usernames:
            queryset = queryset.filter(username__in=usernames)

        total = queryset.count()

        if options["dry_run"]:
            self.stdout.write(
                self.style.WARNING(f"[DRY-RUN] Usuarios a marcar con cambio obligatorio: {total}")
            )
            return

        updated = queryset.update(must_change_password=True, password_changed_at=None)

        self.stdout.write(
            self.style.SUCCESS(
                f"Usuarios marcados para cambio obligatorio de contraseña: {updated}"
            )
        )
