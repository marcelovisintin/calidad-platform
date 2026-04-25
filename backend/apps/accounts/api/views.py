from django.conf import settings
from django.db.models import Q
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenRefreshView

from apps.accounts.api.serializers import (
    ChangePasswordSerializer,
    CurrentUserSerializer,
    LoginSerializer,
    LogoutSerializer,
    RoleSummarySerializer,
    UserAccessProfileSerializer,
    UserAccessProfileWriteSerializer,
    UserDetailSerializer,
    UserListSerializer,
    UserWriteSerializer,
)
from apps.accounts.constants import USER_SCOPE_OPTIONS
from apps.accounts.models import Role, User
from apps.accounts.permissions import CanCreateUsers, CanDeleteUsers, CanEditUsers, CanListUsers
from apps.accounts.services.authorization import filter_user_directory_queryset
from apps.accounts.throttling import LoginRateThrottle


def build_user_queryset(for_user):
    queryset = (
        User.objects.select_related("primary_sector", "primary_sector__site")
        .prefetch_related("role_scopes__role", "role_scopes__site", "role_scopes__area")
        .order_by("first_name", "last_name", "username")
    )
    return filter_user_directory_queryset(queryset, for_user)


class AccountsApiRootAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        base_path = f"/api/{settings.API_VERSION}/accounts/"
        return Response(
            {
                "login": f"{base_path}login/",
                "refresh": f"{base_path}refresh/",
                "logout": f"{base_path}logout/",
                "change_password": f"{base_path}change-password/",
                "me": f"{base_path}me/",
                "users": f"{base_path}users/",
                "user_detail": f"{base_path}users/<uuid:user_id>/",
            }
        )


class LoginAPIView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [LoginRateThrottle]

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)


class RefreshTokenAPIView(TokenRefreshView):
    permission_classes = [AllowAny]


class LogoutAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ChangePasswordAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(CurrentUserSerializer(user).data, status=status.HTTP_200_OK)


class CurrentUserAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = (
            User.objects.select_related("primary_sector", "primary_sector__site")
            .prefetch_related("role_scopes__role", "role_scopes__site", "role_scopes__area")
            .get(pk=request.user.pk)
        )
        serializer = CurrentUserSerializer(user)
        return Response(serializer.data)


class UserManagementAPIView(generics.ListCreateAPIView):
    def get_permissions(self):
        if self.request.method == "POST":
            return [CanCreateUsers()]
        return [CanListUsers()]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return UserWriteSerializer
        return UserListSerializer

    def get_queryset(self):
        queryset = build_user_queryset(self.request.user)

        active_value = self.request.query_params.get("active")
        if active_value is not None:
            is_active = active_value.strip().lower() in {"1", "true", "yes", "y", "on"}
            queryset = queryset.filter(is_active=is_active)

        search_value = self.request.query_params.get("q")
        if search_value:
            search = search_value.strip()
            queryset = queryset.filter(
                Q(username__icontains=search)
                | Q(email__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(employee_code__icontains=search)
            )

        return queryset


class UserDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    lookup_field = "pk"

    def get_permissions(self):
        if self.request.method in {"PUT", "PATCH"}:
            return [CanEditUsers()]
        if self.request.method == "DELETE":
            return [CanDeleteUsers()]
        return [CanListUsers()]

    def get_serializer_class(self):
        if self.request.method in {"PUT", "PATCH"}:
            return UserWriteSerializer
        return UserDetailSerializer

    def get_queryset(self):
        return build_user_queryset(self.request.user)

    def perform_destroy(self, instance):
        if instance.pk == self.request.user.pk:
            raise ValidationError({"detail": "No puede eliminar su propio usuario."})
        instance.delete()


class UserAccessOptionsAPIView(APIView):
    permission_classes = [CanListUsers]

    def get(self, request):
        return Response(
            {
                "access_levels": [
                    {"value": value, "label": label}
                    for value, label in User.AccessLevel.choices
                ],
                "roles": RoleSummarySerializer(Role.objects.filter(is_active=True).order_by("name"), many=True).data,
                "scope_options": USER_SCOPE_OPTIONS,
            }
        )


class UserAccessProfileAPIView(APIView):
    def get_permissions(self):
        if self.request.method == "PATCH":
            return [CanEditUsers()]
        return [CanListUsers()]

    def get_user(self, pk):
        queryset = build_user_queryset(self.request.user).prefetch_related("user_permissions__content_type", "role_scopes__role__permissions__content_type")
        try:
            return queryset.get(pk=pk)
        except User.DoesNotExist as exc:
            raise ValidationError({"user": "Usuario no encontrado o fuera de alcance."}) from exc

    def get(self, request, pk):
        user = self.get_user(pk)
        return Response(UserAccessProfileSerializer(user).data)

    def patch(self, request, pk):
        user = self.get_user(pk)
        serializer = UserAccessProfileWriteSerializer(
            data=request.data,
            context={"request": request, "user": user},
        )
        serializer.is_valid(raise_exception=True)
        updated_user = serializer.save()
        refreshed_user = (
            build_user_queryset(request.user)
            .prefetch_related("user_permissions__content_type", "role_scopes__role__permissions__content_type")
            .get(pk=updated_user.pk)
        )
        return Response(UserAccessProfileSerializer(refreshed_user).data)
