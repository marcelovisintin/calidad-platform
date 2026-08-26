from uuid import UUID

from django.db.models import Exists, OuterRef, Prefetch, Q
from django.db.models.functions import Trim
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.actions.api.treatment_serializers import (
    TreatmentAddAnomalySerializer,
    TreatmentAddParticipantSerializer,
    TreatmentAddRootCauseSerializer,
    TreatmentAddTaskSerializer,
    TreatmentCandidateSerializer,
    TreatmentCreateSerializer,
    TreatmentDetailSerializer,
    TreatmentEvidenceSerializer,
    TreatmentEvidenceWriteSerializer,
    TreatmentLearnedLessonWriteSerializer,
    TreatmentListSerializer,
    TreatmentParticipantSerializer,
    TreatmentParticipantOptionSerializer,
    TreatmentRootCauseSerializer,
    TreatmentTaskEvidenceSerializer,
    TreatmentTaskEvidenceWriteSerializer,
    TreatmentTaskSerializer,
    TreatmentTaskHistorySerializer,
    TreatmentUpdateSerializer,
    TreatmentUpdateTaskSerializer,
    TreatmentValidateSerializer,
)
from apps.actions.models import (
    Treatment,
    TreatmentAnomaly,
    TreatmentEffectivenessValidationResult,
    TreatmentEvidence,
    TreatmentLearnedLessonEvidence,
    TreatmentParticipant,
    TreatmentRootCause,
    TreatmentStatus,
    TreatmentTask,
    TreatmentTaskAnomaly,
    TreatmentTaskEvidence,
)
from apps.actions.services import (
    add_root_cause,
    add_treatment_anomaly,
    add_treatment_evidence,
    add_treatment_participant,
    add_treatment_task,
    add_treatment_task_evidence,
    can_update_treatment_task,
    create_treatment,
    ensure_anomaly_available_for_treatment,
    is_open_treatment_for_association,
    has_global_treatment_management_access,
    save_treatment_learned_lesson,
    update_treatment,
    update_treatment_task,
    validate_treatment_effectiveness,
)
from apps.anomalies.models import AnomalyAttachment, AnomalyStatus, ObservationResolutionPath
from apps.anomalies.selectors import build_anomaly_queryset, filter_anomaly_queryset_for_user
from apps.anomalies.services.classification_rules import immediate_action_q
from common.query_params import parse_iso_date_parameter



def _is_admin_access(user) -> bool:
    return has_global_treatment_management_access(user)



def _visible_treatments_queryset(user):
    queryset = Treatment.objects.all()
    if _is_admin_access(user):
        return queryset

    return queryset.filter(
        Q(created_by=user)
        | Q(primary_anomaly__reporter=user)
        | Q(primary_anomaly__owner=user)
        | Q(participants__user=user)
        | Q(tasks__responsible=user)
        | Q(effectiveness_responsible=user)
    ).distinct()


def _visible_treatment_tasks_queryset(user):
    queryset = TreatmentTask.objects.all()
    if _is_admin_access(user):
        return queryset
    return queryset.filter(responsible=user)


def _validation_ready_treatments_queryset(queryset, user):
    blank_root_causes = (
        TreatmentRootCause.objects.filter(treatment=OuterRef("pk"))
        .annotate(clean_description=Trim("description"))
        .filter(clean_description="")
    )
    incomplete_tasks = TreatmentTask.objects.filter(treatment=OuterRef("pk")).exclude(status="completed")

    queryset = (
        queryset.filter(
            scheduled_for__lt=timezone.now(),
            root_causes__isnull=False,
            effectiveness_evaluation_date__isnull=False,
            effectiveness_responsible__isnull=False,
        )
        .exclude(effectiveness_validation_result=TreatmentEffectivenessValidationResult.EFFECTIVE)
        .annotate(
            has_blank_root_cause=Exists(blank_root_causes),
            has_incomplete_tasks=Exists(incomplete_tasks),
        )
        .filter(has_blank_root_cause=False, has_incomplete_tasks=False)
        .distinct()
    )

    queryset = queryset.filter(effectiveness_responsible=user)

    return queryset


def _treatment_candidate_queryset(visible):
    return (
        visible.filter(
            severity__isnull=False,
            initial_verification__isnull=False,
            classification__requires_action_plan=True,
        )
        .filter(
            ~immediate_action_q()
            | Q(observation_resolution_path=ObservationResolutionPath.TREATMENT_PENDING)
        )
        .exclude(current_status__in=[AnomalyStatus.CLOSED, AnomalyStatus.CANCELLED])
    )


def _open_treatments_for_anomaly(user, anomaly):
    linked_to_anomaly = TreatmentAnomaly.objects.filter(anomaly=anomaly).values("treatment_id")
    return (
        _visible_treatments_queryset(user)
        .filter(status__in=[TreatmentStatus.PENDING, TreatmentStatus.SCHEDULED, TreatmentStatus.IN_PROGRESS])
        .filter(effectiveness_validation_result="")
        .exclude(pk__in=linked_to_anomaly)
        .select_related("primary_anomaly", "primary_anomaly__reporter", "primary_anomaly__area", "primary_anomaly__imputed_area", "primary_anomaly__anomaly_origin")
        .distinct()
        .order_by("-updated_at", "-created_at")
    )


class TreatmentEvidenceDownloadAPIView(APIView):
    def get(self, request, evidence_id):
        visible_treatments = _visible_treatments_queryset(request.user)
        evidence = get_object_or_404(
            TreatmentEvidence.objects.select_related("treatment"),
            pk=evidence_id,
            treatment_id__in=visible_treatments.values("id"),
        )
        if not evidence.file:
            raise Http404("Evidencia sin archivo asociado.")

        response = FileResponse(
            evidence.file.open("rb"),
            as_attachment=True,
            filename=evidence.original_name or evidence.file.name.rsplit("/", 1)[-1],
        )
        if evidence.content_type:
            response["Content-Type"] = evidence.content_type
        return response


class TreatmentTaskEvidenceDownloadAPIView(APIView):
    def get(self, request, evidence_id):
        visible_tasks = _visible_treatment_tasks_queryset(request.user)
        evidence = get_object_or_404(
            TreatmentTaskEvidence.objects.select_related("treatment_task", "treatment_task__treatment"),
            pk=evidence_id,
            treatment_task_id__in=visible_tasks.values("id"),
        )
        if not evidence.file:
            raise Http404("Evidencia sin archivo asociado.")

        response = FileResponse(
            evidence.file.open("rb"),
            as_attachment=True,
            filename=evidence.original_name or evidence.file.name.rsplit("/", 1)[-1],
        )
        if evidence.content_type:
            response["Content-Type"] = evidence.content_type
        return response


class TreatmentLearnedLessonEvidenceDownloadAPIView(APIView):
    def get(self, request, evidence_id):
        visible_treatments = _visible_treatments_queryset(request.user)
        evidence = get_object_or_404(
            TreatmentLearnedLessonEvidence.objects.select_related("learned_lesson", "learned_lesson__treatment"),
            pk=evidence_id,
            learned_lesson__treatment_id__in=visible_treatments.values("id"),
        )
        if not evidence.file:
            raise Http404("Evidencia sin archivo asociado.")

        response = FileResponse(
            evidence.file.open("rb"),
            as_attachment=True,
            filename=evidence.original_name or evidence.file.name.rsplit("/", 1)[-1],
        )
        if evidence.content_type:
            response["Content-Type"] = evidence.content_type
        return response


class TreatmentViewSet(viewsets.ModelViewSet):
    http_method_names = ["get", "post", "put", "patch", "head", "options"]

    def _request_id(self) -> str:
        return self.request.headers.get("X-Request-ID") or self.request.headers.get("X-Request-Id") or ""

    def _is_admin_access(self, user) -> bool:
        return _is_admin_access(user)

    def _visible_anomalies(self):
        return filter_anomaly_queryset_for_user(build_anomaly_queryset(detailed=False), self.request.user)

    def get_queryset(self):
        anomaly_attachment_prefetch = Prefetch(
            "anomaly__attachments",
            queryset=AnomalyAttachment.objects.select_related("uploaded_by").order_by("-created_at"),
        )
        queryset = (
            Treatment.objects.select_related(
                "primary_anomaly",
                "primary_anomaly__reporter",
                "primary_anomaly__area",
                "primary_anomaly__anomaly_origin",
                "effectiveness_responsible",
                "effectiveness_validated_by",
            )
            .prefetch_related(
                Prefetch(
                    "primary_anomaly__attachments",
                    queryset=AnomalyAttachment.objects.select_related("uploaded_by").order_by("-created_at"),
                ),
                Prefetch(
                    "evidences",
                    queryset=TreatmentEvidence.objects.select_related("uploaded_by").order_by("-created_at"),
                ),
                Prefetch(
                    "participants",
                    queryset=TreatmentParticipant.objects.select_related("user").order_by("created_at"),
                ),
                Prefetch(
                    "anomaly_links",
                    queryset=TreatmentAnomaly.objects.select_related(
                        "anomaly",
                        "anomaly__reporter",
                        "anomaly__area",
                        "anomaly__anomaly_origin",
                    )
                    .prefetch_related(anomaly_attachment_prefetch)
                    .order_by("-is_primary", "created_at"),
                ),
                Prefetch(
                    "root_causes",
                    queryset=TreatmentRootCause.objects.order_by("sequence", "created_at"),
                ),
                Prefetch(
                    "tasks",
                    queryset=TreatmentTask.objects.select_related("responsible", "root_cause").prefetch_related(
                        "root_causes",
                        Prefetch(
                            "evidences",
                            queryset=TreatmentTaskEvidence.objects.select_related("uploaded_by").order_by("-created_at"),
                        ),
                        Prefetch(
                            "anomaly_links",
                            queryset=TreatmentTaskAnomaly.objects.select_related(
                                "anomaly",
                                "anomaly__reporter",
                                "anomaly__area",
                                "anomaly__anomaly_origin",
                            ).prefetch_related(anomaly_attachment_prefetch),
                        ),
                    ),
                ),
            )
        )

        search_term = self.request.query_params.get("search", "").strip()
        if search_term:
            queryset = queryset.filter(
                Q(code__icontains=search_term)
                | Q(primary_anomaly__code__icontains=search_term)
                | Q(primary_anomaly__title__icontains=search_term)
                | Q(primary_anomaly__description__icontains=search_term)
                | Q(primary_anomaly__reporter__username__icontains=search_term)
                | Q(primary_anomaly__reporter__first_name__icontains=search_term)
                | Q(primary_anomaly__reporter__last_name__icontains=search_term)
                | Q(primary_anomaly__area__name__icontains=search_term)
                | Q(primary_anomaly__anomaly_origin__name__icontains=search_term)
            )

        user = self.request.user
        if not self._is_admin_access(user):
            queryset = queryset.filter(
                Q(created_by=user)
                | Q(primary_anomaly__reporter=user)
                | Q(primary_anomaly__owner=user)
                | Q(participants__user=user)
                | Q(tasks__responsible=user)
                | Q(effectiveness_responsible=user)
            ).distinct()

        if self.request.query_params.get("validation_ready") in {"1", "true", "True"}:
            queryset = _validation_ready_treatments_queryset(queryset, user)

        return queryset

    def get_serializer_class(self):
        if self.action == "list":
            return TreatmentListSerializer
        if self.action == "create":
            return TreatmentCreateSerializer
        if self.action in {"update", "partial_update"}:
            return TreatmentUpdateSerializer
        if self.action == "add_anomaly":
            return TreatmentAddAnomalySerializer
        if self.action == "add_participant":
            return TreatmentAddParticipantSerializer
        if self.action == "add_root_cause":
            return TreatmentAddRootCauseSerializer
        if self.action == "add_task":
            return TreatmentAddTaskSerializer
        if self.action == "update_task":
            return TreatmentUpdateTaskSerializer
        if self.action == "add_evidence":
            return TreatmentEvidenceWriteSerializer
        if self.action == "add_task_evidence":
            return TreatmentTaskEvidenceWriteSerializer
        if self.action == "validate_effectiveness":
            return TreatmentValidateSerializer
        return TreatmentDetailSerializer

    @action(detail=True, methods=["get"], url_path="participant-options")
    def participant_options(self, request, pk=None):
        self.get_object()
        queryset = (
            User.objects.filter(is_active=True)
            .select_related("primary_sector", "primary_sector__site")
            .order_by("first_name", "last_name", "username")
        )
        serializer = TreatmentParticipantOptionSerializer(
            queryset,
            many=True,
            context=self.get_serializer_context(),
        )
        return Response(serializer.data)

    def _detail_response(self, treatment_id, *, response_status=status.HTTP_200_OK):
        instance = self.get_queryset().get(pk=treatment_id)
        serializer = TreatmentDetailSerializer(instance, context=self.get_serializer_context())
        return Response(serializer.data, status=response_status)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        primary_anomaly = serializer.validated_data["primary_anomaly"]
        if not self._visible_anomalies().filter(pk=primary_anomaly.pk).exists():
            raise PermissionDenied("No tiene alcance para crear tratamiento sobre esa anomalia.")
        ensure_anomaly_available_for_treatment(primary_anomaly, field="primary_anomaly")
        data = dict(serializer.validated_data)
        force_create_new = data.pop("force_create_new", False)
        if not force_create_new and _open_treatments_for_anomaly(request.user, primary_anomaly).exists():
            raise ValidationError(
                {
                    "primary_anomaly": (
                        "Existe un tratamiento abierto disponible para esta anomalia. "
                        "Debe asociarla a un tratamiento abierto en lugar de crear uno nuevo."
                    )
                }
            )

        treatment = create_treatment(
            primary_anomaly=primary_anomaly,
            user=request.user,
            data=data,
            request_id=self._request_id(),
        )
        return self._detail_response(treatment.pk, response_status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        treatment = update_treatment(
            treatment=instance,
            user=request.user,
            data=dict(serializer.validated_data),
            request_id=self._request_id(),
        )
        return self._detail_response(treatment.pk)

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    @action(detail=False, methods=["get"], url_path="tasks-history")
    def tasks_history(self, request):
        queryset = TreatmentTask.objects.select_related(
            "treatment",
            "treatment__primary_anomaly",
            "treatment__primary_anomaly__reporter",
            "treatment__primary_anomaly__area",
            "treatment__primary_anomaly__anomaly_origin",
            "responsible",
            "root_cause",
        ).prefetch_related(
            "root_causes",
            Prefetch(
                "evidences",
                queryset=TreatmentTaskEvidence.objects.select_related("uploaded_by").order_by("-created_at"),
            ),
            Prefetch(
                "anomaly_links",
                queryset=TreatmentTaskAnomaly.objects.select_related(
                    "anomaly",
                    "anomaly__reporter",
                    "anomaly__area",
                    "anomaly__anomaly_origin",
                ).order_by("created_at"),
            ),
        )

        queryset = queryset.filter(responsible=request.user)

        if query_text := (request.query_params.get("q") or "").strip():
            queryset = queryset.filter(
                Q(code__icontains=query_text)
                | Q(title__icontains=query_text)
                | Q(description__icontains=query_text)
                | Q(treatment__code__icontains=query_text)
                | Q(responsible__username__icontains=query_text)
                | Q(responsible__first_name__icontains=query_text)
                | Q(responsible__last_name__icontains=query_text)
                | Q(anomaly_links__anomaly__code__icontains=query_text)
                | Q(anomaly_links__anomaly__title__icontains=query_text)
                | Q(treatment__primary_anomaly__code__icontains=query_text)
                | Q(treatment__primary_anomaly__title__icontains=query_text)
            )

        if anomaly_value := (request.query_params.get("anomaly") or "").strip():
            try:
                anomaly_uuid = UUID(anomaly_value)
                queryset = queryset.filter(
                    Q(anomaly_links__anomaly_id=anomaly_uuid)
                    | Q(treatment__primary_anomaly_id=anomaly_uuid)
                )
            except ValueError:
                queryset = queryset.filter(
                    Q(anomaly_links__anomaly__code__icontains=anomaly_value)
                    | Q(anomaly_links__anomaly__title__icontains=anomaly_value)
                    | Q(treatment__primary_anomaly__code__icontains=anomaly_value)
                    | Q(treatment__primary_anomaly__title__icontains=anomaly_value)
                )

        if treatment_value := (request.query_params.get("treatment") or "").strip():
            try:
                queryset = queryset.filter(treatment_id=UUID(treatment_value))
            except ValueError:
                queryset = queryset.filter(treatment__code__icontains=treatment_value)

        if performed_by := (request.query_params.get("performed_by") or "").strip():
            queryset = queryset.filter(responsible_id=performed_by)

        if completed_on_value := (request.query_params.get("completed_on") or "").strip():
            completed_on = parse_iso_date_parameter(completed_on_value, field_name="completed_on")
            queryset = queryset.filter(execution_date=completed_on)

        status_value = (request.query_params.get("status") or "").strip()
        if status_value == "overdue":
            queryset = queryset.filter(
                status__in=["pending", "in_progress"],
                execution_date__lt=timezone.localdate(),
            )
        elif status_value:
            queryset = queryset.filter(status=status_value)
        else:
            queryset = queryset.filter(status__in=["pending", "in_progress"])

        queryset = queryset.distinct().order_by("-updated_at", "-created_at")

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = TreatmentTaskHistorySerializer(page, many=True, context=self.get_serializer_context())
            return self.get_paginated_response(serializer.data)

        serializer = TreatmentTaskHistorySerializer(queryset, many=True, context=self.get_serializer_context())
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="candidates")
    def candidates(self, request):
        visible = self._visible_anomalies()

        candidate_qs = _treatment_candidate_queryset(visible)

        if treatment_value := (request.query_params.get("treatment") or "").strip():
            try:
                treatment_id = UUID(treatment_value)
            except ValueError:
                candidate_qs = candidate_qs.none()
            else:
                if not _visible_treatments_queryset(request.user).filter(pk=treatment_id).exists():
                    raise PermissionDenied("No tiene alcance sobre el tratamiento seleccionado.")

                linked_to_treatment = TreatmentAnomaly.objects.filter(treatment_id=treatment_id).values("anomaly_id")
                candidate_qs = candidate_qs.exclude(pk__in=linked_to_treatment)
        else:
            treatment_anomaly_ids = TreatmentAnomaly.objects.values("anomaly_id")
            candidate_qs = candidate_qs.exclude(pk__in=treatment_anomaly_ids)

        if anomaly_value := (request.query_params.get("anomaly") or "").strip():
            try:
                candidate_qs = candidate_qs.filter(pk=UUID(anomaly_value))
            except ValueError:
                candidate_qs = candidate_qs.filter(
                    Q(code__icontains=anomaly_value)
                    | Q(title__icontains=anomaly_value)
                    | Q(description__icontains=anomaly_value)
                )

        if sector_value := (request.query_params.get("sector") or "").strip():
            candidate_qs = candidate_qs.filter(
                Q(site__code__icontains=sector_value)
                | Q(site__name__icontains=sector_value)
            )

        if area_value := (request.query_params.get("area") or "").strip():
            candidate_qs = candidate_qs.filter(
                Q(area__code__icontains=area_value)
                | Q(area__name__icontains=area_value)
            )

        if user_value := (request.query_params.get("user") or "").strip():
            try:
                candidate_qs = candidate_qs.filter(reporter_id=UUID(user_value))
            except ValueError:
                candidate_qs = candidate_qs.filter(
                    Q(reporter__username__icontains=user_value)
                    | Q(reporter__first_name__icontains=user_value)
                    | Q(reporter__last_name__icontains=user_value)
                    | Q(reporter__email__icontains=user_value)
                )

        if date_from_value := (request.query_params.get("date_from") or "").strip():
            date_from = parse_iso_date_parameter(date_from_value, field_name="date_from")
            candidate_qs = candidate_qs.filter(detected_at__date__gte=date_from)

        if date_to_value := (request.query_params.get("date_to") or "").strip():
            date_to = parse_iso_date_parameter(date_to_value, field_name="date_to")
            candidate_qs = candidate_qs.filter(detected_at__date__lte=date_to)

        candidate_qs = candidate_qs.select_related("reporter", "area", "imputed_area", "anomaly_origin").distinct().order_by("-detected_at", "code")

        page = self.paginate_queryset(candidate_qs)
        if page is not None:
            output = TreatmentCandidateSerializer(page, many=True, context=self.get_serializer_context())
            return self.get_paginated_response(output.data)

        output = TreatmentCandidateSerializer(candidate_qs, many=True, context=self.get_serializer_context())
        return Response(output.data)

    @action(detail=False, methods=["get"], url_path="open-options")
    def open_options(self, request):
        anomaly_value = (request.query_params.get("anomaly") or "").strip()
        if not anomaly_value:
            raise ValidationError({"anomaly": "Debe indicar una anomalia."})

        try:
            anomaly_id = UUID(anomaly_value)
        except ValueError:
            raise ValidationError({"anomaly": "Identificador de anomalia invalido."})

        visible = self._visible_anomalies()
        anomaly = get_object_or_404(_treatment_candidate_queryset(visible), pk=anomaly_id)
        ensure_anomaly_available_for_treatment(anomaly)

        queryset = _open_treatments_for_anomaly(request.user, anomaly)

        serializer = TreatmentListSerializer(queryset, many=True, context=self.get_serializer_context())
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="anomalies")
    def add_anomaly(self, request, pk=None):
        treatment = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        anomaly = serializer.validated_data["anomaly"]

        if not self._visible_anomalies().filter(pk=anomaly.pk).exists():
            raise PermissionDenied("No tiene alcance sobre la anomalia a asociar.")
        if not is_open_treatment_for_association(treatment):
            raise ValidationError({"treatment": "Solo se pueden asociar anomalias a tratamientos abiertos y no validados."})

        link = add_treatment_anomaly(
            treatment=treatment,
            anomaly=anomaly,
            user=request.user,
            request_id=self._request_id(),
        )
        output = TreatmentCandidateSerializer(link.anomaly, context=self.get_serializer_context())
        return Response(output.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="participants")
    def add_participant(self, request, pk=None):
        treatment = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        participant = add_treatment_participant(
            treatment=treatment,
            participant_user=serializer.validated_data["user"],
            role=serializer.validated_data.get("role") or "convoked",
            note=serializer.validated_data.get("note", ""),
            user=request.user,
            request_id=self._request_id(),
        )
        output = TreatmentParticipantSerializer(participant, context=self.get_serializer_context())
        return Response(output.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="root-causes")
    def add_root_cause(self, request, pk=None):
        treatment = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        root_cause = add_root_cause(
            treatment=treatment,
            description=serializer.validated_data["description"],
            user=request.user,
            request_id=self._request_id(),
        )
        output = TreatmentRootCauseSerializer(root_cause, context=self.get_serializer_context())
        return Response(output.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="tasks")
    def add_task(self, request, pk=None):
        treatment = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)

        root_causes = list(data.get("root_cause_ids") or [])
        if data.get("root_cause"):
            root_causes.append(data["root_cause"])
        if not root_causes:
            raise ValidationError({"root_cause_ids": "Debe seleccionar al menos una causa raiz."})
        if any(root_cause.treatment_id != treatment.id for root_cause in root_causes):
            raise ValidationError({"root_cause_ids": "Todas las causas raiz deben pertenecer al tratamiento."})

        task = add_treatment_task(
            treatment=treatment,
            data=data,
            user=request.user,
            request_id=self._request_id(),
        )
        output = TreatmentTaskSerializer(task, context=self.get_serializer_context())
        return Response(output.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["patch"], url_path=r"tasks/(?P<task_id>[^/.]+)")
    def update_task(self, request, pk=None, task_id=None):
        treatment = self.get_object()
        task = TreatmentTask.objects.filter(treatment=treatment, pk=task_id).first()
        if not task:
            raise ValidationError({"task": "La tarea no pertenece al tratamiento indicado."})
        if not can_update_treatment_task(request.user, task):
            raise PermissionDenied("Solo puede modificar tareas asignadas a su usuario.")

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)

        root_causes = list(data.get("root_cause_ids") or [])
        if data.get("root_cause"):
            root_causes.append(data["root_cause"])
        if "root_cause_ids" in data or "root_cause" in data:
            if not root_causes:
                raise ValidationError({"root_cause_ids": "Debe seleccionar al menos una causa raiz."})
            if any(root_cause.treatment_id != treatment.id for root_cause in root_causes):
                raise ValidationError({"root_cause_ids": "Todas las causas raiz deben pertenecer al tratamiento."})

        updated = update_treatment_task(
            treatment_task=task,
            data=data,
            user=request.user,
            request_id=self._request_id(),
        )
        output = TreatmentTaskSerializer(updated, context=self.get_serializer_context())
        return Response(output.data)

    @action(detail=True, methods=["post"], url_path="validation")
    def validate_effectiveness(self, request, pk=None):
        treatment = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated = validate_treatment_effectiveness(
            treatment=treatment,
            user=request.user,
            result=serializer.validated_data["result"],
            comment=serializer.validated_data.get("comment", ""),
            request_id=self._request_id(),
        )
        return self._detail_response(validated.pk)

    @action(
        detail=True,
        methods=["post"],
        url_path="evidences",
        parser_classes=[MultiPartParser, FormParser],
    )
    def add_evidence(self, request, pk=None):
        treatment = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        evidence = add_treatment_evidence(
            treatment=treatment,
            user=request.user,
            data=dict(serializer.validated_data),
            request_id=self._request_id(),
        )
        output = TreatmentEvidenceSerializer(evidence, context=self.get_serializer_context())
        return Response(output.data, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=["post"],
        url_path=r"tasks/(?P<task_id>[^/.]+)/evidences",
        parser_classes=[MultiPartParser, FormParser],
    )
    def add_task_evidence(self, request, pk=None, task_id=None):
        treatment = self.get_object()
        task = TreatmentTask.objects.filter(treatment=treatment, pk=task_id).first()
        if not task:
            raise ValidationError({"task": "La tarea no pertenece al tratamiento indicado."})
        if not can_update_treatment_task(request.user, task):
            raise PermissionDenied("Solo puede cargar evidencias en tareas asignadas a su usuario.")

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        evidence = add_treatment_task_evidence(
            treatment_task=task,
            user=request.user,
            data=dict(serializer.validated_data),
            request_id=self._request_id(),
        )
        output = TreatmentTaskEvidenceSerializer(evidence, context=self.get_serializer_context())
        return Response(output.data, status=status.HTTP_201_CREATED)


class TreatmentTrackingViewSet(viewsets.ReadOnlyModelViewSet):
    http_method_names = ["get", "head", "options"]
    serializer_class = TreatmentDetailSerializer

    def get_serializer_class(self):
        if self.action == "list":
            return TreatmentListSerializer
        return TreatmentDetailSerializer

    def get_queryset(self):
        anomaly_attachment_prefetch = Prefetch(
            "anomaly__attachments",
            queryset=AnomalyAttachment.objects.select_related("uploaded_by").order_by("-created_at"),
        )
        queryset = (
            _visible_treatments_queryset(self.request.user)
            .select_related(
                "primary_anomaly",
                "primary_anomaly__reporter",
                "primary_anomaly__area",
                "primary_anomaly__anomaly_origin",
                "effectiveness_responsible",
                "effectiveness_validated_by",
            )
            .prefetch_related(
                Prefetch(
                    "primary_anomaly__attachments",
                    queryset=AnomalyAttachment.objects.select_related("uploaded_by").order_by("-created_at"),
                ),
                Prefetch(
                    "evidences",
                    queryset=TreatmentEvidence.objects.select_related("uploaded_by").order_by("-created_at"),
                ),
                Prefetch(
                    "participants",
                    queryset=TreatmentParticipant.objects.select_related("user").order_by("created_at"),
                ),
                Prefetch(
                    "anomaly_links",
                    queryset=TreatmentAnomaly.objects.select_related(
                        "anomaly",
                        "anomaly__reporter",
                        "anomaly__area",
                        "anomaly__anomaly_origin",
                    )
                    .prefetch_related(anomaly_attachment_prefetch)
                    .order_by("-is_primary", "created_at"),
                ),
                Prefetch(
                    "root_causes",
                    queryset=TreatmentRootCause.objects.order_by("sequence", "created_at"),
                ),
                Prefetch(
                    "tasks",
                    queryset=TreatmentTask.objects.select_related("responsible", "root_cause")
                    .prefetch_related(
                        "root_causes",
                        Prefetch(
                            "evidences",
                            queryset=TreatmentTaskEvidence.objects.select_related("uploaded_by").order_by("-created_at"),
                        ),
                        Prefetch(
                            "anomaly_links",
                            queryset=TreatmentTaskAnomaly.objects.select_related(
                                "anomaly",
                                "anomaly__reporter",
                                "anomaly__area",
                                "anomaly__anomaly_origin",
                            ).prefetch_related(anomaly_attachment_prefetch),
                        ),
                    )
                    .order_by("execution_date", "created_at"),
                ),
            )
            .distinct()
        )

        if code := (self.request.query_params.get("code") or "").strip():
            queryset = queryset.filter(Q(code__icontains=code) | Q(primary_anomaly__code__icontains=code))

        if user_value := (self.request.query_params.get("user") or "").strip():
            try:
                user_uuid = UUID(user_value)
                queryset = queryset.filter(
                    Q(created_by_id=user_uuid)
                    | Q(primary_anomaly__reporter_id=user_uuid)
                    | Q(participants__user_id=user_uuid)
                    | Q(tasks__responsible_id=user_uuid)
                    | Q(effectiveness_responsible_id=user_uuid)
                    | Q(effectiveness_validated_by_id=user_uuid)
                )
            except ValueError:
                queryset = queryset.filter(
                    Q(created_by__username__icontains=user_value)
                    | Q(created_by__first_name__icontains=user_value)
                    | Q(created_by__last_name__icontains=user_value)
                    | Q(primary_anomaly__reporter__username__icontains=user_value)
                    | Q(primary_anomaly__reporter__first_name__icontains=user_value)
                    | Q(primary_anomaly__reporter__last_name__icontains=user_value)
                    | Q(participants__user__username__icontains=user_value)
                    | Q(participants__user__first_name__icontains=user_value)
                    | Q(participants__user__last_name__icontains=user_value)
                    | Q(tasks__responsible__username__icontains=user_value)
                    | Q(tasks__responsible__first_name__icontains=user_value)
                    | Q(tasks__responsible__last_name__icontains=user_value)
                    | Q(effectiveness_responsible__username__icontains=user_value)
                    | Q(effectiveness_responsible__first_name__icontains=user_value)
                    | Q(effectiveness_responsible__last_name__icontains=user_value)
                )

        if process := (self.request.query_params.get("process") or "").strip():
            try:
                process_uuid = UUID(process)
                queryset = queryset.filter(
                    Q(primary_anomaly__area_id=process_uuid)
                    | Q(anomaly_links__anomaly__area_id=process_uuid)
                )
            except ValueError:
                queryset = queryset.filter(
                    Q(primary_anomaly__area__code__icontains=process)
                    | Q(primary_anomaly__area__name__icontains=process)
                    | Q(primary_anomaly__anomaly_origin__code__icontains=process)
                    | Q(primary_anomaly__anomaly_origin__name__icontains=process)
                    | Q(anomaly_links__anomaly__area__code__icontains=process)
                    | Q(anomaly_links__anomaly__area__name__icontains=process)
                    | Q(anomaly_links__anomaly__anomaly_origin__code__icontains=process)
                    | Q(anomaly_links__anomaly__anomaly_origin__name__icontains=process)
                )

        return queryset.distinct().order_by("-updated_at", "-created_at")


class TreatmentLearnedLessonViewSet(viewsets.ReadOnlyModelViewSet):
    http_method_names = ["get", "patch", "head", "options"]
    parser_classes = [MultiPartParser, FormParser]
    serializer_class = TreatmentListSerializer

    def _request_id(self) -> str:
        return self.request.headers.get("X-Request-ID") or self.request.headers.get("X-Request-Id") or ""

    def get_serializer_class(self):
        if self.action == "partial_update":
            return TreatmentLearnedLessonWriteSerializer
        return TreatmentListSerializer

    def get_queryset(self):
        queryset = (
            _visible_treatments_queryset(self.request.user)
            .filter(effectiveness_validation_result=TreatmentEffectivenessValidationResult.EFFECTIVE)
            .select_related(
                "primary_anomaly",
                "primary_anomaly__reporter",
                "primary_anomaly__area",
                "primary_anomaly__anomaly_origin",
                "effectiveness_responsible",
                "effectiveness_validated_by",
                "learned_lesson",
                "learned_lesson__saved_by",
            )
            .prefetch_related(
                Prefetch(
                    "learned_lesson__evidences",
                    queryset=TreatmentLearnedLessonEvidence.objects.select_related("uploaded_by").order_by("-created_at"),
                )
            )
        )

        if search := (self.request.query_params.get("search") or "").strip():
            queryset = queryset.filter(
                Q(code__icontains=search)
                | Q(primary_anomaly__code__icontains=search)
                | Q(primary_anomaly__title__icontains=search)
                | Q(primary_anomaly__area__name__icontains=search)
            )

        return queryset.distinct().order_by("-effectiveness_validated_at", "-updated_at")

    def partial_update(self, request, *args, **kwargs):
        treatment = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        files = request.FILES.getlist("evidences")
        save_treatment_learned_lesson(
            treatment=treatment,
            user=request.user,
            data=dict(serializer.validated_data),
            files=files,
            request_id=self._request_id(),
        )
        output = TreatmentListSerializer(self.get_queryset().get(pk=treatment.pk), context=self.get_serializer_context())
        return Response(output.data)
