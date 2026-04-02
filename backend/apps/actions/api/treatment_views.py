from django.db.models import Prefetch, Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from apps.actions.api.treatment_serializers import (
    TreatmentAddAnomalySerializer,
    TreatmentAddParticipantSerializer,
    TreatmentAddRootCauseSerializer,
    TreatmentAddTaskSerializer,
    TreatmentCandidateSerializer,
    TreatmentCreateSerializer,
    TreatmentDetailSerializer,
    TreatmentListSerializer,
    TreatmentParticipantSerializer,
    TreatmentRootCauseSerializer,
    TreatmentTaskSerializer,
    TreatmentUpdateSerializer,
    TreatmentUpdateTaskSerializer,
)
from apps.actions.models import (
    Treatment,
    TreatmentAnomaly,
    TreatmentParticipant,
    TreatmentRootCause,
    TreatmentTask,
    TreatmentTaskAnomaly,
)
from apps.actions.services import (
    add_root_cause,
    add_treatment_anomaly,
    add_treatment_participant,
    add_treatment_task,
    create_treatment,
    update_treatment,
    update_treatment_task,
)
from apps.anomalies.models import AnomalyStage, AnomalyStatus
from apps.anomalies.selectors import build_anomaly_queryset, filter_anomaly_queryset_for_user


class TreatmentViewSet(viewsets.ModelViewSet):
    http_method_names = ["get", "post", "put", "patch", "head", "options"]

    def _request_id(self) -> str:
        return self.request.headers.get("X-Request-ID") or self.request.headers.get("X-Request-Id") or ""

    def _is_admin_access(self, user) -> bool:
        return bool(user and user.is_authenticated and (user.is_superuser or getattr(user, "access_level", "") in {"administrador", "desarrollador"}))

    def _visible_anomalies(self):
        return filter_anomaly_queryset_for_user(build_anomaly_queryset(detailed=False), self.request.user)

    def get_queryset(self):
        queryset = (
            Treatment.objects.select_related(
                "primary_anomaly",
                "primary_anomaly__reporter",
                "primary_anomaly__area",
                "primary_anomaly__anomaly_origin",
            )
            .prefetch_related(
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
                    ).order_by("-is_primary", "created_at"),
                ),
                Prefetch(
                    "root_causes",
                    queryset=TreatmentRootCause.objects.order_by("sequence", "created_at"),
                ),
                Prefetch(
                    "tasks",
                    queryset=TreatmentTask.objects.select_related("responsible", "root_cause").prefetch_related(
                        Prefetch(
                            "anomaly_links",
                            queryset=TreatmentTaskAnomaly.objects.select_related(
                                "anomaly",
                                "anomaly__reporter",
                                "anomaly__area",
                                "anomaly__anomaly_origin",
                            ),
                        )
                    ),
                ),
            )
        )

        user = self.request.user
        if self._is_admin_access(user):
            return queryset

        return queryset.filter(
            Q(created_by=user)
            | Q(primary_anomaly__reporter=user)
            | Q(participants__user=user)
            | Q(tasks__responsible=user)
        ).distinct()

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
        return TreatmentDetailSerializer

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

        treatment = create_treatment(
            primary_anomaly=primary_anomaly,
            user=request.user,
            data=dict(serializer.validated_data),
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

    @action(detail=False, methods=["get"], url_path="candidates")
    def candidates(self, request):
        visible = self._visible_anomalies()
        treatment_anomaly_ids = TreatmentAnomaly.objects.values("anomaly_id")

        candidate_qs = (
            visible.filter(
                Q(severity__isnull=False)
                | Q(classification__requires_action_plan=True)
                | Q(current_status=AnomalyStatus.IN_TREATMENT)
                | Q(current_stage__in=[AnomalyStage.ACTION_PLAN, AnomalyStage.EXECUTION_AND_FOLLOW_UP, AnomalyStage.RESULTS])
            )
            .exclude(current_status__in=[AnomalyStatus.CLOSED, AnomalyStatus.CANCELLED])
            .exclude(pk__in=treatment_anomaly_ids)
            .select_related("reporter", "area", "anomaly_origin")
            .order_by("-detected_at")
        )
        page = self.paginate_queryset(candidate_qs)
        if page is not None:
            output = TreatmentCandidateSerializer(page, many=True, context=self.get_serializer_context())
            return self.get_paginated_response(output.data)

        output = TreatmentCandidateSerializer(candidate_qs, many=True, context=self.get_serializer_context())
        return Response(output.data)

    @action(detail=True, methods=["post"], url_path="anomalies")
    def add_anomaly(self, request, pk=None):
        treatment = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        anomaly = serializer.validated_data["anomaly"]

        if not self._visible_anomalies().filter(pk=anomaly.pk).exists():
            raise PermissionDenied("No tiene alcance sobre la anomalia a asociar.")

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

        root_cause = data.get("root_cause")
        if root_cause and root_cause.treatment_id != treatment.id:
            raise ValidationError({"root_cause": "La causa raiz no pertenece al tratamiento."})

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

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)

        root_cause = data.get("root_cause")
        if root_cause and root_cause.treatment_id != treatment.id:
            raise ValidationError({"root_cause": "La causa raiz no pertenece al tratamiento."})

        updated = update_treatment_task(
            treatment_task=task,
            data=data,
            user=request.user,
            request_id=self._request_id(),
        )
        output = TreatmentTaskSerializer(updated, context=self.get_serializer_context())
        return Response(output.data)


