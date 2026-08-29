from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from apps.indicators.models import IndicatorReport, IndicatorReportStatus


class Command(BaseCommand):
    help = "Elimina PDF entregados o vencidos conservando la auditoria del informe."

    def handle(self, *args, **options):
        reports = IndicatorReport.objects.filter(
            Q(status=IndicatorReportStatus.COMPLETED) | Q(expires_at__lte=timezone.now())
        ).exclude(report_file="")
        removed = 0
        for report in reports.iterator():
            if report.report_file:
                report.report_file.delete(save=False)
                report.report_file = None
                report.expires_at = None
                report.save(update_fields=["report_file", "expires_at", "updated_at"])
                removed += 1
        self.stdout.write(self.style.SUCCESS(f"Archivos PDF vencidos eliminados: {removed}"))
