from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import CanAssignAction
from apps.actions.api.serializers import (
    ActionEvidenceSerializer,
    ActionEvidenceWriteSerializer,
    ActionItemDetailSerializer,
    ActionItemListSerializer,
    ActionItemTransitionSerializer,
    ActionItemUpdateSerializer,
    ActionItemWriteSerializer,
    ActionPlanDetailSerializer,
    ActionPlanListSerializer,
    ActionPlanTransitionSerializer,
    ActionPlanUpdateSerializer,
    ActionPlanWriteSerializer,
    ActionsApiRootSerializer,
)
from apps.actions.models import ActionEvidence
from apps.actions.selectors import (
    OPEN_ACTION_ITEM_STATUSES,
    apply_action_item_filters,
    build_action_item_queryset,
    build_action_plan_queryset,
    filter_action_item_queryset_for_user,
    filter_action_plan_queryset_for_user,
    my_action_items_queryset,
)
from apps.actions.services import (
    add_action_evidence,
    create_action_item,
    create_action_plan,
    transition_action_item,
    transition_action_plan,
    update_action_item,
    update_action_plan,
)


class ActionsApiRootView(APIView):
    def get(self, request):
        payload = {
            "plans": "/api/v1/actions/plans/",
            "items": "/api/v1/actions/items/",
            "my_actions": "/api/v1/actions/items/my-actions/",
            "pending": "/api/v1/actions/items/pending/",
            "treatments": "/api/v1/actions/treatments/",
        }
        serializer = ActionsApiRootSerializer(payload)
        return Response(serializer.data)


class ActionEvidenceDownloadAPIView(APIView):
    def get(self, request, evidence_id):
        visible_items = filter_action_item_queryset_for_user(build_action_item_queryset(detailed=False), request.user)
        evidence = get_object_or_404(
            ActionEvidence.objects.select_related("action_item"),
            pk=evidence_id,
            action_item_id__in=visible_items.values("id"),
        )
        if not evidence.file:
            raise Http404("Evidencia sin archivo asociado.")

        response = FileResponse(
            evidence.file.open("rb"),
            as_attachment=True,
            filename=evidence.file.name.rsplit("/", 1)[-1],
        )
        return response


class ActionPlanViewSet(viewsets.ModelViewSet):
    http_method_names = ["get", "post", "put", "patch", "head", "options"]

    def get_permissions(self):
        if self.action in {"create", "update", "partial_update", "transition", "add_item"}:
            return [CanAssignAction()]
        return super().get_permissions()

    def _with_counts(self, queryset):
        open_filter = Q(items__status__in=OPEN_ACTION_ITEM_STATUSES)
        overdue_filter = Q(items__status__in=OPEN_ACTION_ITEM_STATUSES, items__due_date__lt=timezone.localdate())
        return queryset.annotate(
            items_count=Count("items", distinct=True),
            pending_items_count=Count("items", filter=open_filter, distinct=True),
            overdue_items_count=Count("items", filter=overdue_filter, distinct=True),
        )

    def get_queryset(self):
        detailed_actions = {"retrieve", "transition", "add_item"}
        queryset = build_action_plan_queryset(detailed=self.action in detailed_actions)
        queryset = filter_action_plan_queryset_for_user(queryset, self.request.user)
        queryset = self._with_counts(queryset)

        params = self.request.query_params
        if anomaly_id := params.get("anomaly"):
            queryset = queryset.filter(anomaly_id=anomaly_id)
        if status_value := params.get("status"):
            queryset = queryset.filter(status=status_value)
        if owner_id := params.get("owner"):
            queryset = queryset.filter(owner_id=owner_id)
        return queryset

    def get_serializer_class(self):
        if self.action == "list":
            return ActionPlanListSerializer
        if self.action == "create":
            return ActionPlanWriteSerializer
        if self.action in {"update", "partial_update"}:
            return ActionPlanUpdateSerializer
        if self.action == "transition":
            return ActionPlanTransitionSerializer
        if self.action == "add_item":
            return ActionItemWriteSerializer
        return ActionPlanDetailSerializer

    def _request_id(self) -> str:
        return self.request.headers.get("X-Request-ID") or self.request.headers.get("X-Request-Id") or ""

    def _detail_response(self, action_plan_id, *, response_status=status.HTTP_200_OK):
        queryset = filter_action_plan_queryset_for_user(build_action_plan_queryset(detailed=True), self.request.user)
        instance = self._with_counts(queryset).get(pk=action_plan_id)
        serializer = ActionPlanDetailSerializer(instance, context=self.get_serializer_context())
        return Response(serializer.data, status=response_status)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        anomaly = serializer.validated_data["anomaly"]
        data = {key: value for key, value in serializer.validated_data.items() if key != "anomaly"}
        action_plan = create_action_plan(
            anomaly=anomaly,
            user=request.user,
            data=data,
            request_id=self._request_id(),
        )
        return self._detail_response(action_plan.pk, response_status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        action_plan = update_action_plan(
            action_plan=instance,
            user=request.user,
            data=dict(serializer.validated_data),
            request_id=self._request_id(),
        )
        return self._detail_response(action_plan.pk)

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    @action(detail=True, methods=["post"], url_path="transition")
    def transition(self, request, pk=None):
        action_plan = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = transition_action_plan(
            action_plan=action_plan,
            user=request.user,
            request_id=self._request_id(),
            **serializer.validated_data,
        )
        return self._detail_response(updated.pk)

    @action(detail=True, methods=["post"], url_path="items")
    def add_item(self, request, pk=None):
        action_plan = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = create_action_item(
            action_plan=action_plan,
            user=request.user,
            data=dict(serializer.validated_data),
            request_id=self._request_id(),
        )
        output = ActionItemDetailSerializer(item, context=self.get_serializer_context())
        return Response(output.data, status=status.HTTP_201_CREATED)


class ActionItemViewSet(viewsets.ModelViewSet):
    http_method_names = ["get", "post", "put", "patch", "head", "options"]

    def get_permissions(self):
        if self.action in {"update", "partial_update"}:
            return [CanAssignAction()]
        return super().get_permissions()

    def get_queryset(self):
        detailed_actions = {"retrieve", "add_evidence", "transition", "my_actions", "pending"}
        queryset = build_action_item_queryset(detailed=self.action in detailed_actions)
        queryset = filter_action_item_queryset_for_user(queryset, self.request.user)
        return apply_action_item_filters(queryset, self.request.query_params)

    def get_serializer_class(self):
        if self.action in {"update", "partial_update"}:
            return ActionItemUpdateSerializer
        if self.action == "transition":
            return ActionItemTransitionSerializer
        if self.action == "add_evidence":
            return ActionEvidenceWriteSerializer
        if self.action in {"retrieve", "my_actions", "pending"}:
            return ActionItemDetailSerializer
        return ActionItemListSerializer

    def _request_id(self) -> str:
        return self.request.headers.get("X-Request-ID") or self.request.headers.get("X-Request-Id") or ""

    def _detail_response(self, action_item_id, *, response_status=status.HTTP_200_OK):
        queryset = filter_action_item_queryset_for_user(build_action_item_queryset(detailed=True), self.request.user)
        instance = queryset.get(pk=action_item_id)
        serializer = ActionItemDetailSerializer(instance, context=self.get_serializer_context())
        return Response(serializer.data, status=response_status)

    def create(self, request, *args, **kwargs):
        return self.http_method_not_allowed(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        action_item = update_action_item(
            action_item=instance,
            user=request.user,
            data=dict(serializer.validated_data),
            request_id=self._request_id(),
        )
        return self._detail_response(action_item.pk)

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    @action(detail=False, methods=["get"], url_path="my-actions")
    def my_actions(self, request):
        queryset = my_action_items_queryset(request.user, detailed=True)
        queryset = apply_action_item_filters(queryset, request.query_params)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = ActionItemDetailSerializer(page, many=True, context=self.get_serializer_context())
            return self.get_paginated_response(serializer.data)
        serializer = ActionItemDetailSerializer(queryset, many=True, context=self.get_serializer_context())
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="pending")
    def pending(self, request):
        queryset = my_action_items_queryset(request.user, detailed=True, pending_only=True)
        queryset = apply_action_item_filters(queryset, request.query_params)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = ActionItemDetailSerializer(page, many=True, context=self.get_serializer_context())
            return self.get_paginated_response(serializer.data)
        serializer = ActionItemDetailSerializer(queryset, many=True, context=self.get_serializer_context())
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="transition")
    def transition(self, request, pk=None):
        action_item = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = transition_action_item(
            action_item=action_item,
            user=request.user,
            request_id=self._request_id(),
            **serializer.validated_data,
        )
        return self._detail_response(updated.pk)

    @action(
        detail=True,
        methods=["post"],
        url_path="evidences",
        parser_classes=[MultiPartParser, FormParser],
    )
    def add_evidence(self, request, pk=None):
        action_item = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        evidence = add_action_evidence(
            action_item=action_item,
            user=request.user,
            data=dict(serializer.validated_data),
            request_id=self._request_id(),
        )
        output = ActionEvidenceSerializer(evidence, context=self.get_serializer_context())
        return Response(output.data, status=status.HTTP_201_CREATED)
