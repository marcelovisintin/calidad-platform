import csv

from django.db.models import Q
from datetime import date, datetime, time
import unicodedata

from django.db.models import Case, Count, IntegerField, Sum, Value, When
from django.db.models.functions import Coalesce, Lower
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import CanCreateAnomaly, CanEditAnomaly
from apps.anomalies.api.serializers import (
    AnomalyAttachmentSerializer,
    AnomalyAttachmentWriteSerializer,
    AffectedOrderListSerializer,
    AnomalyCauseAnalysisSerializer,
    AnomalyCodeReservationSerializer,
    AnomalyCauseAnalysisWriteSerializer,
    AnomalyClassificationSerializer,
    AnomalyClassificationWriteSerializer,
    AnomalyCommentCreateSerializer,
    AnomalyCommentSerializer,
    AnomalyCreateSerializer,
    AnomalyDetailSerializer,
    AnomalyEffectivenessCheckSerializer,
    AnomalyEffectivenessCheckWriteSerializer,
    AnomalyImmediateActionWriteSerializer,
    AnomalyInitialVerificationSerializer,
    AnomalyInitialVerificationWriteSerializer,
    AnomalyLearningSerializer,
    AnomalyLearningWriteSerializer,
    AnomalyListSerializer,
    AnomalyObservationActionWriteSerializer,
    AnomalyObservationLoadWriteSerializer,
    AnomalyObservationVerificationWriteSerializer,
    AnomalyParticipantSerializer,
    AnomalyParticipantWriteSerializer,
    AnomalyProposalSerializer,
    AnomalyProposalWriteSerializer,
    AnomalyTransitionSerializer,
    AnomalyUpdateSerializer,
    WorkflowMetadataSerializer,
)
from apps.anomalies.models import (
    AffectedOrder,
    AnalysisMethod,
    Anomaly,
    AnomalyAttachment,
    AnomalyCommentType,
    AnomalyStage,
    AnomalyStatus,
    ObservationResolutionPath,
    ParticipantRole,
)
from apps.anomalies.selectors import build_anomaly_queryset, filter_anomaly_queryset_for_user
from apps.anomalies.services import (
    add_attachment,
    add_comment,
    add_participant,
    add_proposal,
    create_anomaly,
    record_effectiveness_check,
    reserve_anomaly_code,
    save_cause_analysis,
    save_classification,
    save_immediate_action,
    unlock_classification_change,
    save_initial_verification,
    save_learning,
    save_observation_action_taken,
    save_observation_load,
    transition_anomaly,
    update_anomaly,
    verify_observation_effectiveness,
)
from apps.anomalies.services.classification_rules import immediate_action_q
from common.pagination import DefaultPageNumberPagination


STATUS_SEARCH_LABELS = {
    AnomalyStatus.REGISTERED: "registrado",
    AnomalyStatus.IN_EVALUATION: "en evaluacion",
    AnomalyStatus.IN_ANALYSIS: "en analisis",
    AnomalyStatus.IN_TREATMENT: "en tratamiento",
    AnomalyStatus.PENDING_VERIFICATION: "pendiente de verificacion",
    AnomalyStatus.CLOSED: "cerrado",
    AnomalyStatus.CANCELLED: "cancelado",
    AnomalyStatus.REOPENED: "reabierto",
}


def is_admin_access_user(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    return bool(user.is_superuser or getattr(user, "access_level", "") in {"administrador", "desarrollador"})


def normalize_search_text(value: str) -> str:
    without_accents = unicodedata.normalize("NFKD", value)
    ascii_value = "".join(char for char in without_accents if not unicodedata.combining(char))
    return " ".join(ascii_value.lower().replace("_", " ").split())


def matching_anomaly_status_values(term: str) -> list[str]:
    normalized_term = normalize_search_text(term)
    if not normalized_term:
        return []

    matches: list[str] = []
    for status_value, status_label in AnomalyStatus.choices:
        candidates = {
            status_value,
            status_value.replace("_", " "),
            status_label,
            STATUS_SEARCH_LABELS.get(status_value, ""),
        }
        if any(normalized_term in normalize_search_text(candidate) for candidate in candidates):
            matches.append(status_value)
    return matches


def build_tracking_search_query(term: str) -> Q:
    query = (
        Q(code__icontains=term)
        | Q(title__icontains=term)
        | Q(area__code__icontains=term)
        | Q(area__name__icontains=term)
        | Q(affected_orders__number__icontains=term)
        | Q(affected_orders__order_type__code__icontains=term)
    )
    if status_values := matching_anomaly_status_values(term):
        query |= Q(current_status__in=status_values)
    return query


TRACKING_FILTER_PARAMS = {"search", "status", "stage", "site", "area", "owner", "ordering", "order", "order_by"}


def has_active_tracking_filter(params) -> bool:
    return any((params.get(name) or "").strip() for name in TRACKING_FILTER_PARAMS)


def apply_default_tracking_order(queryset):
    return queryset.annotate(
        status_sort_priority=Case(
            When(current_status=AnomalyStatus.REGISTERED, then=Value(0)),
            When(current_status=AnomalyStatus.CLOSED, then=Value(2)),
            default=Value(1),
            output_field=IntegerField(),
        )
    ).order_by("status_sort_priority", "-detected_at", "code")


class AnomalyWorkflowMetadataAPIView(APIView):
    def get(self, request):
        payload = {
            "statuses": {value: label for value, label in AnomalyStatus.choices},
            "stages": {value: label for value, label in AnomalyStage.choices},
            "analysis_methods": {value: label for value, label in AnalysisMethod.choices},
            "participant_roles": {value: label for value, label in ParticipantRole.choices},
            "comment_types": {value: label for value, label in AnomalyCommentType.choices},
        }
        serializer = WorkflowMetadataSerializer(payload)
        return Response(serializer.data)


class AnomalyAttachmentDownloadAPIView(APIView):
    def get(self, request, attachment_id):
        visible_anomalies = filter_anomaly_queryset_for_user(build_anomaly_queryset(detailed=False), request.user)
        attachment = get_object_or_404(
            AnomalyAttachment.objects.select_related("anomaly"),
            pk=attachment_id,
            anomaly_id__in=visible_anomalies.values("id"),
        )
        if not attachment.file:
            raise Http404("Adjunto sin archivo asociado.")

        response = FileResponse(
            attachment.file.open("rb"),
            as_attachment=True,
            filename=attachment.original_name or attachment.file.name.rsplit("/", 1)[-1],
        )
        if attachment.content_type:
            response["Content-Type"] = attachment.content_type
        return response


class AnomalyRepetitionStudyAPIView(APIView):
    http_method_names = ["get", "head", "options"]

    def _is_admin_user(self, user) -> bool:
        if not user or not user.is_authenticated:
            return False
        access_level = getattr(user, "access_level", "")
        return user.is_superuser or access_level in {"administrador", "desarrollador"}

    def get(self, request):
        if not self._is_admin_user(request.user):
            return Response(
                {"detail": "Esta consulta esta disponible solo para usuarios administradores."},
                status=status.HTTP_403_FORBIDDEN,
            )

        date_from_value = (request.query_params.get("date_from") or "").strip()
        if not date_from_value:
            return Response(
                {"date_from": "Debe seleccionar Desde fecha antes de ejecutar el analisis."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            date_from = date.fromisoformat(date_from_value)
        except ValueError:
            return Response(
                {"date_from": "La fecha ingresada no es valida."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        current_date = timezone.localdate()
        if date_from > current_date:
            return Response(
                {"date_from": "Desde fecha no puede ser posterior al dia actual."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        current_timezone = timezone.get_current_timezone()
        start_at = timezone.make_aware(datetime.combine(date_from, time.min), current_timezone)
        end_at = timezone.now()
        queryset = (
            filter_anomaly_queryset_for_user(build_anomaly_queryset(detailed=False), request.user)
            .filter(created_at__gte=start_at, created_at__lte=end_at)
            .order_by("-created_at", "-detected_at")
        )

        by_type = list(
            queryset.values("anomaly_type_id", "anomaly_type__name")
            .annotate(count=Count("id"))
            .order_by("-count", "anomaly_type__name")
        )
        by_type_sector = list(
            queryset.annotate(
                assigned_area_id=Coalesce("imputed_area_id", "area_id"),
                assigned_area_name=Coalesce("imputed_area__name", "area__name"),
            )
            .values(
                "anomaly_type_id",
                "anomaly_type__name",
                "assigned_area_id",
                "assigned_area_name",
                "severity_id",
                "severity__name",
            )
            .annotate(count=Count("id"))
            .order_by("-count", "anomaly_type__name", "assigned_area_name", "severity__name")
        )

        anomalies = [
            {
                "id": str(anomaly.id),
                "code": anomaly.code,
                "title": anomaly.title,
                "observations": anomaly.description,
                "anomaly_type": {
                    "id": str(anomaly.anomaly_type_id),
                    "name": anomaly.anomaly_type.name,
                },
                "sector": {
                    "id": str(anomaly.imputed_area_id or anomaly.area_id),
                    "name": (anomaly.imputed_area.name if anomaly.imputed_area_id else anomaly.area.name),
                },
                "finding_type": {
                    "id": str(anomaly.severity_id or ""),
                    "name": anomaly.severity.name if anomaly.severity_id else "Sin tipo de hallazgo",
                },
                "registered_at": anomaly.created_at,
            }
            for anomaly in queryset
        ]

        return Response(
            {
                "date_from": date_from.isoformat(),
                "date_to": current_date.isoformat(),
                "total": queryset.count(),
                "by_type": [
                    {
                        "type_id": str(item["anomaly_type_id"]),
                        "type_name": item["anomaly_type__name"] or "Sin tipo de desvio",
                        "count": item["count"],
                    }
                    for item in by_type
                ],
                "by_type_sector": [
                    {
                        "type_id": str(item["anomaly_type_id"]),
                        "type_name": item["anomaly_type__name"] or "Sin tipo de desvio",
                        "sector_id": str(item["assigned_area_id"] or ""),
                        "sector_name": item["assigned_area_name"] or "Sin asignado a",
                        "finding_type_id": str(item["severity_id"] or ""),
                        "finding_type_name": item["severity__name"] or "Sin tipo de hallazgo",
                        "count": item["count"],
                    }
                    for item in by_type_sector
                ],
                "anomalies": anomalies,
            }
        )


class AffectedOrderListAPIView(APIView):
    ordering_fields = {
        "detected_at": "anomaly__detected_at",
        "type": "order_type__display_order",
        "number": "number",
        "quantity": "quantity",
        "anomaly": "anomaly__code",
        "process": "anomaly__area__name",
    }

    def _parse_quantity(self, raw_value: str | None, field_name: str):
        if raw_value in {None, ""}:
            return None
        try:
            value = int(raw_value)
        except (TypeError, ValueError) as exc:
            raise ValidationError({field_name: "Debe ser un numero entero."}) from exc
        if value < 0:
            raise ValidationError({field_name: "No puede ser negativo."})
        return value

    def _parse_date(self, raw_value: str | None, field_name: str):
        if not raw_value:
            return None
        try:
            return date.fromisoformat(raw_value)
        except ValueError as exc:
            raise ValidationError({field_name: "Use el formato AAAA-MM-DD."}) from exc

    def _filtered_queryset(self, request):
        visible_anomalies = filter_anomaly_queryset_for_user(Anomaly.objects.all(), request.user)
        queryset = AffectedOrder.objects.filter(anomaly__in=visible_anomalies).select_related(
            "order_type",
            "anomaly",
            "anomaly__area",
            "anomaly__area__site",
        )
        params = request.query_params

        if order_type_id := params.get("order_type"):
            queryset = queryset.filter(order_type_id=order_type_id)
        if number := (params.get("number") or "").strip():
            queryset = queryset.filter(number__icontains=number)
        if anomaly_term := (params.get("anomaly") or "").strip():
            queryset = queryset.filter(
                Q(anomaly__code__icontains=anomaly_term) | Q(anomaly__title__icontains=anomaly_term)
            )
        if area_id := params.get("area"):
            queryset = queryset.filter(anomaly__area_id=area_id)
        if status_value := params.get("status"):
            queryset = queryset.filter(anomaly__current_status=status_value)

        quantity_min = self._parse_quantity(params.get("quantity_min"), "quantity_min")
        quantity_max = self._parse_quantity(params.get("quantity_max"), "quantity_max")
        if quantity_min is not None:
            queryset = queryset.filter(quantity__gte=quantity_min)
        if quantity_max is not None:
            queryset = queryset.filter(quantity__lte=quantity_max)
        if quantity_min is not None and quantity_max is not None and quantity_min > quantity_max:
            raise ValidationError({"quantity_max": "Debe ser mayor o igual que la cantidad minima."})

        date_from = self._parse_date(params.get("date_from"), "date_from")
        date_to = self._parse_date(params.get("date_to"), "date_to")
        if date_from:
            queryset = queryset.filter(anomaly__detected_at__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(anomaly__detected_at__date__lte=date_to)
        if date_from and date_to and date_from > date_to:
            raise ValidationError({"date_to": "Debe ser posterior o igual a la fecha desde."})

        if search := (params.get("search") or "").strip():
            queryset = queryset.filter(
                Q(number__icontains=search)
                | Q(order_type__code__icontains=search)
                | Q(order_type__name__icontains=search)
                | Q(anomaly__code__icontains=search)
                | Q(anomaly__title__icontains=search)
                | Q(anomaly__area__code__icontains=search)
                | Q(anomaly__area__name__icontains=search)
            )

        ordering_param = (params.get("ordering") or "-detected_at").strip()
        descending = ordering_param.startswith("-")
        ordering_key = ordering_param[1:] if descending else ordering_param
        ordering_field = self.ordering_fields.get(ordering_key, "anomaly__detected_at")
        if descending:
            ordering_field = f"-{ordering_field}"
        return queryset.order_by(ordering_field, "order_type__display_order", "number", "id")

    def _totals(self, queryset):
        aggregate = queryset.aggregate(total_quantity=Sum("quantity"))
        by_type = list(
            queryset.values("order_type_id", "order_type__code", "order_type__name")
            .annotate(records=Count("id"), total_quantity=Sum("quantity"))
            .order_by("order_type__display_order", "order_type__name")
        )
        return {
            "records": queryset.count(),
            "unique_orders": queryset.annotate(normalized_number=Lower("number"))
            .values("order_type_id", "normalized_number")
            .distinct()
            .count(),
            "anomalies": queryset.values("anomaly_id").distinct().count(),
            "total_quantity": aggregate["total_quantity"] or 0,
            "by_type": [
                {
                    "order_type_id": str(item["order_type_id"]),
                    "code": item["order_type__code"],
                    "name": item["order_type__name"],
                    "records": item["records"],
                    "total_quantity": item["total_quantity"] or 0,
                }
                for item in by_type
            ],
        }

    def _csv_response(self, queryset):
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="ordenes-afectadas.csv"'
        response.write("\ufeff")
        writer = csv.writer(response, delimiter=";")
        writer.writerow(
            ["Tipo", "Numero", "Cantidad", "Anomalia", "Titulo", "Proceso", "Fecha", "Estado"]
        )
        for item in queryset.iterator():
            writer.writerow(
                [
                    item.order_type.code,
                    item.number,
                    item.quantity,
                    item.anomaly.code,
                    item.anomaly.title,
                    item.anomaly.area.name,
                    item.anomaly.detected_at.isoformat(),
                    item.anomaly.current_status,
                ]
            )
        return response

    def get(self, request):
        queryset = self._filtered_queryset(request)
        if (request.query_params.get("export") or "").strip().lower() == "csv":
            return self._csv_response(queryset)

        totals = self._totals(queryset)
        paginator = DefaultPageNumberPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        serializer = AffectedOrderListSerializer(page, many=True)
        response = paginator.get_paginated_response(serializer.data)
        response.data["totals"] = totals
        return response


class AnomalyViewSet(viewsets.ModelViewSet):
    http_method_names = ["get", "post", "put", "patch", "head", "options"]

    def get_permissions(self):
        if self.action in {"create", "reserve_code"}:
            return [CanCreateAnomaly()]
        if self.action in {"update", "partial_update"}:
            return [CanEditAnomaly()]
        return super().get_permissions()

    def get_queryset(self):
        detailed_actions = {
            "retrieve",
            "transition",
            "add_comment",
            "add_participant",
            "save_initial_verification",
            "save_classification",
            "unlock_classification_change",
            "save_cause_analysis",
            "add_proposal",
            "record_effectiveness_check",
            "save_learning",
            "save_immediate_action",
            "add_attachment",
        }
        queryset = build_anomaly_queryset(detailed=self.action in detailed_actions)
        queryset = filter_anomaly_queryset_for_user(queryset, self.request.user)

        params = self.request.query_params
        if status_value := params.get("status"):
            queryset = queryset.filter(current_status=status_value)
        if stage_value := params.get("stage"):
            queryset = queryset.filter(current_stage=stage_value)
        if site_id := params.get("site"):
            queryset = queryset.filter(site_id=site_id)
        if area_id := params.get("area"):
            queryset = queryset.filter(area_id=area_id)
        if owner_id := params.get("owner"):
            queryset = queryset.filter(owner_id=owner_id)
        if reporter_id := params.get("reporter"):
            queryset = queryset.filter(reporter_id=reporter_id)
        if term := params.get("search"):
            queryset = queryset.filter(build_tracking_search_query(term)).distinct()
        if self.action == "list" and not has_active_tracking_filter(params):
            queryset = apply_default_tracking_order(queryset)

        return queryset

    def get_serializer_class(self):
        if self.action == "list":
            return AnomalyListSerializer
        if self.action == "immediate_actions":
            return AnomalyListSerializer
        if self.action == "reserve_code":
            return AnomalyCodeReservationSerializer
        if self.action == "create":
            return AnomalyCreateSerializer
        if self.action in {"update", "partial_update"}:
            return AnomalyUpdateSerializer
        if self.action == "transition":
            return AnomalyTransitionSerializer
        if self.action == "add_comment":
            return AnomalyCommentCreateSerializer
        if self.action == "add_participant":
            return AnomalyParticipantWriteSerializer
        if self.action == "save_initial_verification":
            return AnomalyInitialVerificationWriteSerializer
        if self.action == "save_classification":
            return AnomalyClassificationWriteSerializer
        if self.action == "save_cause_analysis":
            return AnomalyCauseAnalysisWriteSerializer
        if self.action == "add_proposal":
            return AnomalyProposalWriteSerializer
        if self.action == "record_effectiveness_check":
            return AnomalyEffectivenessCheckWriteSerializer
        if self.action == "save_learning":
            return AnomalyLearningWriteSerializer
        if self.action == "save_immediate_action":
            return AnomalyImmediateActionWriteSerializer
        if self.action == "save_observation_load":
            return AnomalyObservationLoadWriteSerializer
        if self.action == "save_observation_action_taken":
            return AnomalyObservationActionWriteSerializer
        if self.action == "verify_observation_effectiveness":
            return AnomalyObservationVerificationWriteSerializer
        if self.action == "add_attachment":
            return AnomalyAttachmentWriteSerializer
        return AnomalyDetailSerializer

    def _request_id(self) -> str:
        return (
            self.request.headers.get("X-Request-ID")
            or self.request.headers.get("X-Request-Id")
            or ""
        )

    def _detail_response(self, anomaly_id, *, response_status=status.HTTP_200_OK):
        queryset = filter_anomaly_queryset_for_user(build_anomaly_queryset(detailed=True), self.request.user)
        instance = queryset.get(pk=anomaly_id)
        serializer = AnomalyDetailSerializer(instance, context=self.get_serializer_context())
        return Response(serializer.data, status=response_status)

    @action(detail=False, methods=["post"], url_path="reserve-code")
    def reserve_code(self, request):
        reservation = reserve_anomaly_code(user=request.user)
        serializer = AnomalyCodeReservationSerializer(reservation, context=self.get_serializer_context())
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        anomaly = create_anomaly(
            user=request.user,
            data=dict(serializer.validated_data),
            request_id=self._request_id(),
        )
        return self._detail_response(anomaly.pk, response_status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        anomaly = update_anomaly(
            anomaly=instance,
            user=request.user,
            data=dict(serializer.validated_data),
            request_id=self._request_id(),
        )
        return self._detail_response(anomaly.pk)

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    @action(detail=False, methods=["get"], url_path="immediate-actions")
    def immediate_actions(self, request):
        params = request.query_params
        include_closed = (params.get("include_closed") or "").strip().lower() in {"1", "true", "yes", "si"}
        queryset = (
            filter_anomaly_queryset_for_user(build_anomaly_queryset(detailed=False), request.user)
            .filter(immediate_action_q())
            .exclude(
                observation_resolution_path__in=[
                    ObservationResolutionPath.TREATMENT_PENDING,
                    ObservationResolutionPath.TREATMENT,
                ]
            )
            .distinct()
            .order_by("-detected_at", "-created_at")
        )

        if not is_admin_access_user(request.user):
            queryset = queryset.filter(Q(owner=request.user) | Q(immediate_action__responsible=request.user))

        if not include_closed:
            queryset = queryset.exclude(current_status__in=[AnomalyStatus.CLOSED, AnomalyStatus.CANCELLED])

        if term := params.get("search"):
            queryset = queryset.filter(
                Q(code__icontains=term)
                | Q(title__icontains=term)
                | Q(description__icontains=term)
                | Q(manufacturing_order_number__icontains=term)
                | Q(affected_orders__number__icontains=term)
                | Q(affected_orders__order_type__code__icontains=term)
                | Q(affected_process__icontains=term)
                | Q(reporter__username__icontains=term)
                | Q(reporter__email__icontains=term)
                | Q(reporter__first_name__icontains=term)
                | Q(reporter__last_name__icontains=term)
            )

        page = self.paginate_queryset(queryset)
        serializer = AnomalyListSerializer(page if page is not None else queryset, many=True, context=self.get_serializer_context())
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="immediate-action")
    def save_immediate_action(self, request, pk=None):
        anomaly = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        save_immediate_action(
            anomaly=anomaly,
            user=request.user,
            data=dict(serializer.validated_data),
            request_id=self._request_id(),
        )
        return self._detail_response(anomaly.pk)

    @action(detail=True, methods=["post"], url_path="observation/load")
    def save_observation_load(self, request, pk=None):
        anomaly = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        save_observation_load(
            anomaly=anomaly,
            user=request.user,
            data=dict(serializer.validated_data),
            request_id=self._request_id(),
        )
        return self._detail_response(anomaly.pk)

    @action(detail=True, methods=["post"], url_path="observation/actions-taken")
    def save_observation_action_taken(self, request, pk=None):
        anomaly = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        save_observation_action_taken(
            anomaly=anomaly,
            user=request.user,
            data=dict(serializer.validated_data),
            request_id=self._request_id(),
        )
        return self._detail_response(anomaly.pk)

    @action(detail=True, methods=["post"], url_path="observation/effectiveness")
    def verify_observation_effectiveness(self, request, pk=None):
        anomaly = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        verify_observation_effectiveness(
            anomaly=anomaly,
            user=request.user,
            data=dict(serializer.validated_data),
            request_id=self._request_id(),
        )
        return self._detail_response(anomaly.pk)

    @action(detail=True, methods=["post"], url_path="transition")
    def transition(self, request, pk=None):
        anomaly = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = transition_anomaly(
            anomaly=anomaly,
            user=request.user,
            request_id=self._request_id(),
            **serializer.validated_data,
        )
        return self._detail_response(updated.pk)

    @action(detail=True, methods=["post"], url_path="comments")
    def add_comment(self, request, pk=None):
        anomaly = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        comment = add_comment(
            anomaly=anomaly,
            user=request.user,
            data=dict(serializer.validated_data),
            request_id=self._request_id(),
        )
        output = AnomalyCommentSerializer(comment, context=self.get_serializer_context())
        return Response(output.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="participants")
    def add_participant(self, request, pk=None):
        anomaly = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        participant = add_participant(
            anomaly=anomaly,
            user=request.user,
            data=dict(serializer.validated_data),
            request_id=self._request_id(),
        )
        output = AnomalyParticipantSerializer(participant, context=self.get_serializer_context())
        return Response(output.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="initial-verification")
    def save_initial_verification(self, request, pk=None):
        anomaly = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        verification = save_initial_verification(
            anomaly=anomaly,
            user=request.user,
            data=dict(serializer.validated_data),
            request_id=self._request_id(),
        )
        output = AnomalyInitialVerificationSerializer(verification, context=self.get_serializer_context())
        return Response(output.data)

    @action(detail=True, methods=["post"], url_path="classification")
    def save_classification(self, request, pk=None):
        anomaly = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        classification = save_classification(
            anomaly=anomaly,
            user=request.user,
            data=dict(serializer.validated_data),
            request_id=self._request_id(),
        )
        output = AnomalyClassificationSerializer(classification, context=self.get_serializer_context())
        return Response(output.data)

    
    @action(detail=True, methods=["post"], url_path="classification/unlock")
    def unlock_classification_change(self, request, pk=None):
        anomaly = self.get_object()
        updated = unlock_classification_change(
            anomaly=anomaly,
            user=request.user,
            request_id=self._request_id(),
        )
        return self._detail_response(updated.pk)
    @action(detail=True, methods=["post"], url_path="cause-analysis")
    def save_cause_analysis(self, request, pk=None):
        anomaly = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        analysis = save_cause_analysis(
            anomaly=anomaly,
            user=request.user,
            data=dict(serializer.validated_data),
            request_id=self._request_id(),
        )
        output = AnomalyCauseAnalysisSerializer(analysis, context=self.get_serializer_context())
        return Response(output.data)

    @action(detail=True, methods=["post"], url_path="proposals")
    def add_proposal(self, request, pk=None):
        anomaly = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        proposal = add_proposal(
            anomaly=anomaly,
            user=request.user,
            data=dict(serializer.validated_data),
            request_id=self._request_id(),
        )
        output = AnomalyProposalSerializer(proposal, context=self.get_serializer_context())
        return Response(output.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="effectiveness-checks")
    def record_effectiveness_check(self, request, pk=None):
        anomaly = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        check = record_effectiveness_check(
            anomaly=anomaly,
            user=request.user,
            data=dict(serializer.validated_data),
            request_id=self._request_id(),
        )
        output = AnomalyEffectivenessCheckSerializer(check, context=self.get_serializer_context())
        return Response(output.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="learning")
    def save_learning(self, request, pk=None):
        anomaly = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        learning = save_learning(
            anomaly=anomaly,
            user=request.user,
            data=dict(serializer.validated_data),
            request_id=self._request_id(),
        )
        output = AnomalyLearningSerializer(learning, context=self.get_serializer_context())
        return Response(output.data)

    @action(
        detail=True,
        methods=["post"],
        url_path="attachments",
        parser_classes=[MultiPartParser, FormParser],
    )
    def add_attachment(self, request, pk=None):
        anomaly = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        attachment = add_attachment(
            anomaly=anomaly,
            user=request.user,
            data=dict(serializer.validated_data),
            request_id=self._request_id(),
        )
        output = AnomalyAttachmentSerializer(attachment, context=self.get_serializer_context())
        return Response(output.data, status=status.HTTP_201_CREATED)












