from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.constants import PERMISSION_CLOSE_ANOMALY
from apps.accounts.permissions import CanCreateAnomaly, CanEditAnomaly
from apps.anomalies.api.serializers import (
    AnomalyAttachmentSerializer,
    AnomalyAttachmentWriteSerializer,
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
    AnomalyImmediateActionSerializer,
    AnomalyImmediateActionWriteSerializer,
    AnomalyInitialVerificationSerializer,
    AnomalyInitialVerificationWriteSerializer,
    AnomalyLearningSerializer,
    AnomalyLearningWriteSerializer,
    AnomalyListSerializer,
    AnomalyParticipantSerializer,
    AnomalyParticipantWriteSerializer,
    AnomalyProposalSerializer,
    AnomalyProposalWriteSerializer,
    AnomalyTransitionSerializer,
    AnomalyUpdateSerializer,
    WorkflowMetadataSerializer,
)
from apps.anomalies.models import (
    AnalysisMethod,
    AnomalyAttachment,
    AnomalyCommentType,
    AnomalyStage,
    AnomalyStatus,
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
    transition_anomaly,
    update_anomaly,
)
from apps.anomalies.services.classification_rules import immediate_action_q


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
            queryset = queryset.filter(
                Q(code__icontains=term)
                | Q(title__icontains=term)
                | Q(description__icontains=term)
                | Q(manufacturing_order_number__icontains=term)
                | Q(affected_process__icontains=term)
                | Q(reporter__username__icontains=term)
                | Q(reporter__email__icontains=term)
                | Q(reporter__first_name__icontains=term)
                | Q(reporter__last_name__icontains=term)
            )

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
        if not (request.user.is_superuser or request.user.has_perm(PERMISSION_CLOSE_ANOMALY)):
            return Response({"detail": "No tiene permisos para gestionar accion inmediata."}, status=status.HTTP_403_FORBIDDEN)

        params = request.query_params
        include_closed = (params.get("include_closed") or "").strip().lower() in {"1", "true", "yes", "si"}
        queryset = (
            filter_anomaly_queryset_for_user(build_anomaly_queryset(detailed=False), request.user)
            .filter(immediate_action_q())
            .distinct()
            .order_by("-detected_at", "-created_at")
        )

        if not include_closed:
            queryset = queryset.exclude(current_status__in=[AnomalyStatus.CLOSED, AnomalyStatus.CANCELLED])

        if term := params.get("search"):
            queryset = queryset.filter(
                Q(code__icontains=term)
                | Q(title__icontains=term)
                | Q(description__icontains=term)
                | Q(manufacturing_order_number__icontains=term)
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












