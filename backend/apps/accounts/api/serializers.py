import re

from django.contrib.auth import authenticate
from django.contrib.auth.models import Permission
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.tokens import RefreshToken, TokenError

from apps.accounts.constants import USER_SCOPE_OPTIONS
from apps.accounts.models import Role, User, UserRoleScope
from apps.accounts.services.authorization import get_effective_permissions, get_user_role_codes
from apps.catalog.models import Area, Site

DEFAULT_INITIAL_PASSWORD = "12345678"


class SiteSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Site
        fields = ("id", "code", "name")


class AreaSummarySerializer(serializers.ModelSerializer):
    site = SiteSummarySerializer(read_only=True)

    class Meta:
        model = Area
        fields = ("id", "code", "name", "site")


class RoleSummarySerializer(serializers.ModelSerializer):
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = Role
        fields = ("id", "code", "name", "permissions")

    def get_permissions(self, obj):
        return sorted(
            f"{app_label}.{codename}"
            for app_label, codename in obj.permissions.values_list("content_type__app_label", "codename").distinct()
        )


class UserRoleScopeSerializer(serializers.ModelSerializer):
    role = RoleSummarySerializer(read_only=True)
    site = SiteSummarySerializer(read_only=True)
    area = AreaSummarySerializer(read_only=True)

    class Meta:
        model = UserRoleScope
        fields = ("id", "role", "site", "area")


class CurrentUserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    sector = AreaSummarySerializer(source="primary_sector", read_only=True)
    role_codes = serializers.SerializerMethodField()
    role_scopes = UserRoleScopeSerializer(many=True, read_only=True)
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "employee_code",
            "phone",
            "access_level",
            "must_change_password",
            "password_changed_at",
            "sector",
            "is_active",
            "date_joined",
            "last_login",
            "last_activity_at",
            "role_codes",
            "role_scopes",
            "permissions",
        )

    def get_role_codes(self, obj):
        return get_user_role_codes(obj)

    def get_permissions(self, obj):
        return get_effective_permissions(obj)


class UserListSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    sector = AreaSummarySerializer(source="primary_sector", read_only=True)
    role_codes = serializers.SerializerMethodField()
    primary_sector_id = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "employee_code",
            "phone",
            "access_level",
            "must_change_password",
            "sector",
            "primary_sector_id",
            "is_active",
            "is_staff",
            "date_joined",
            "last_activity_at",
            "role_codes",
        )

    def get_role_codes(self, obj):
        return get_user_role_codes(obj)

    def get_primary_sector_id(self, obj):
        return obj.primary_sector_id


class UserDetailSerializer(UserListSerializer):
    role_scopes = UserRoleScopeSerializer(many=True, read_only=True)

    class Meta(UserListSerializer.Meta):
        fields = UserListSerializer.Meta.fields + (
            "last_login",
            "created_at",
            "updated_at",
            "role_scopes",
        )


def _permission_objects_for_scope_keys(scope_keys: list[str]):
    from apps.accounts.services.role_setup import ensure_required_permissions

    ensure_required_permissions()
    selected_options = [option for option in USER_SCOPE_OPTIONS if option["key"] in set(scope_keys)]
    permission_keys = sorted({permission for option in selected_options for permission in option["permission_keys"]})
    permission_filter = Q()
    for permission_key in permission_keys:
        app_label, codename = permission_key.split(".", 1)
        permission_filter |= Q(content_type__app_label=app_label, codename=codename)
    if not permission_filter.children:
        return Permission.objects.none()
    return Permission.objects.filter(permission_filter)


def _manual_scope_keys_for_user(user: User) -> list[str]:
    manual_permissions = set(user.user_permissions.values_list("content_type__app_label", "codename"))
    resolved = {f"{app_label}.{codename}" for app_label, codename in manual_permissions}
    return [
        option["key"]
        for option in USER_SCOPE_OPTIONS
        if set(option["permission_keys"]).issubset(resolved)
    ]


class UserAccessProfileSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    username = serializers.CharField(read_only=True)
    full_name = serializers.CharField(read_only=True)
    email = serializers.EmailField(read_only=True)
    access_level = serializers.ChoiceField(choices=User.AccessLevel.choices)
    primary_sector = AreaSummarySerializer(read_only=True)
    role = RoleSummarySerializer(read_only=True)
    manual_scope_keys = serializers.SerializerMethodField()
    effective_permissions = serializers.SerializerMethodField()
    role_permissions = serializers.SerializerMethodField()

    def to_representation(self, instance):
        data = super().to_representation(instance)
        scope = instance.role_scopes.select_related("role").order_by("created_at").first()
        data["role"] = RoleSummarySerializer(scope.role).data if scope else None
        return data

    def get_manual_scope_keys(self, obj):
        return _manual_scope_keys_for_user(obj)

    def get_effective_permissions(self, obj):
        return get_effective_permissions(obj)

    def get_role_permissions(self, obj):
        permissions = Permission.objects.filter(
            business_roles__is_active=True,
            business_roles__user_scopes__user=obj,
        ).values_list("content_type__app_label", "codename").distinct()
        return sorted(f"{app_label}.{codename}" for app_label, codename in permissions)


class UserAccessProfileWriteSerializer(serializers.Serializer):
    access_level = serializers.ChoiceField(choices=User.AccessLevel.choices, required=True)
    role = serializers.PrimaryKeyRelatedField(queryset=Role.objects.filter(is_active=True), allow_null=True, required=False)
    manual_scope_keys = serializers.ListField(
        child=serializers.ChoiceField(choices=[(option["key"], option["label"]) for option in USER_SCOPE_OPTIONS]),
        allow_empty=True,
        required=True,
    )

    def validate(self, attrs):
        request = self.context.get("request")
        user: User = self.context["user"]
        target_level = attrs.get("access_level")
        if target_level == User.AccessLevel.DESARROLLADOR and request and not request.user.is_superuser:
            raise serializers.ValidationError(
                {"access_level": "Solo un superusuario puede asignar el nivel desarrollador."}
            )
        if attrs.get("role") is not None and not user.role_scopes.exists() and not user.primary_sector_id:
            raise serializers.ValidationError(
                {"role": "Para asignar un rol desde esta pantalla, el usuario debe tener sector principal."}
            )
        return attrs

    def save(self, **kwargs):
        user: User = self.context["user"]
        access_level = self.validated_data["access_level"]
        role = self.validated_data.get("role")
        manual_scope_keys = self.validated_data["manual_scope_keys"]

        user.access_level = access_level
        user.is_staff = access_level in {User.AccessLevel.ADMINISTRADOR, User.AccessLevel.DESARROLLADOR}
        user.is_superuser = access_level == User.AccessLevel.DESARROLLADOR
        user.save(update_fields=["access_level", "is_staff", "is_superuser", "updated_at"])

        if "role" in self.validated_data:
            scopes = user.role_scopes.select_related("site", "area").order_by("created_at")
            current_scope = scopes.first()
            if role is None:
                scopes.delete()
            elif current_scope:
                current_scope.role = role
                current_scope.full_clean()
                current_scope.save(update_fields=["role", "updated_at"])
            else:
                UserRoleScope.objects.create(
                    user=user,
                    role=role,
                    site=user.primary_sector.site,
                    area=user.primary_sector,
                    created_by=self.context["request"].user,
                    updated_by=self.context["request"].user,
                )

        user.user_permissions.set(_permission_objects_for_scope_keys(manual_scope_keys))
        for cache_name in ("_perm_cache", "_user_perm_cache", "_group_perm_cache", "_role_permissions_cache"):
            if hasattr(user, cache_name):
                delattr(user, cache_name)
        return user


class UserWriteSerializer(serializers.ModelSerializer):
    primary_sector = serializers.PrimaryKeyRelatedField(
        queryset=Area.objects.select_related("site"),
        allow_null=True,
        required=False,
    )
    password = serializers.CharField(write_only=True, required=False, allow_blank=True, min_length=8, trim_whitespace=False)
    access_level = serializers.ChoiceField(
        choices=User.AccessLevel.choices,
        required=False,
    )

    class Meta:
        model = User
        fields = (
            "username",
            "email",
            "first_name",
            "last_name",
            "employee_code",
            "phone",
            "access_level",
            "primary_sector",
            "is_active",
            "password",
        )

    def validate(self, attrs):
        request = self.context.get("request")
        target_level = attrs.get("access_level")
        if target_level == User.AccessLevel.DESARROLLADOR and request and not request.user.is_superuser:
            raise serializers.ValidationError(
                {"access_level": "Solo un superusuario puede asignar el nivel desarrollador."}
            )

        return attrs

    def _apply_access_level_flags(self, validated_data):
        level = validated_data.get("access_level")
        if not level:
            return

        validated_data["is_staff"] = level in {
            User.AccessLevel.ADMINISTRADOR,
            User.AccessLevel.DESARROLLADOR,
        }
        validated_data["is_superuser"] = level == User.AccessLevel.DESARROLLADOR

    def create(self, validated_data):
        password = (validated_data.pop("password", "") or "").strip() or DEFAULT_INITIAL_PASSWORD
        validated_data.setdefault("is_active", True)
        validated_data.setdefault("access_level", User.AccessLevel.USUARIO_ACTIVO)
        validated_data["must_change_password"] = True
        validated_data["password_changed_at"] = None
        self._apply_access_level_flags(validated_data)
        return User.objects.create_user(password=password, **validated_data)

    def update(self, instance, validated_data):
        raw_password = validated_data.pop("password", None)
        password = raw_password.strip() if isinstance(raw_password, str) else None
        self._apply_access_level_flags(validated_data)

        for field, value in validated_data.items():
            setattr(instance, field, value)

        if password:
            instance.set_password(password)
            instance.must_change_password = True
            instance.password_changed_at = None

        instance.save()
        return instance


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True, trim_whitespace=False)
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)
    confirm_password = serializers.CharField(write_only=True, trim_whitespace=False)

    default_error_messages = {
        "invalid_current_password": "La contrasena actual es incorrecta.",
    }

    def validate(self, attrs):
        user = self.context["request"].user
        current_password = attrs["current_password"]
        new_password = attrs["new_password"]
        confirm_password = attrs["confirm_password"]

        if not user.check_password(current_password):
            raise serializers.ValidationError({"current_password": self.error_messages["invalid_current_password"]})

        if new_password != confirm_password:
            raise serializers.ValidationError({"confirm_password": "La confirmacion no coincide con la nueva contrasena."})

        if current_password == new_password:
            raise serializers.ValidationError({"new_password": "La nueva contrasena debe ser distinta a la actual."})

        self._validate_password_strength(user, new_password)
        return attrs

    def _validate_password_strength(self, user: User, password: str):
        if len(password) < 10:
            raise serializers.ValidationError({"new_password": "Debe tener al menos 10 caracteres."})

        if not re.search(r"[A-Z]", password):
            raise serializers.ValidationError({"new_password": "Debe incluir al menos una letra mayuscula."})

        if not re.search(r"[a-z]", password):
            raise serializers.ValidationError({"new_password": "Debe incluir al menos una letra minuscula."})

        if not re.search(r"\d", password):
            raise serializers.ValidationError({"new_password": "Debe incluir al menos un numero."})

        if not re.search(r"[^A-Za-z0-9]", password):
            raise serializers.ValidationError({"new_password": "Debe incluir al menos un caracter especial."})

        lower_password = password.lower()
        username_lower = (user.username or "").lower()
        email_local_lower = (user.email.split("@")[0] if user.email else "").lower()

        if username_lower and username_lower in lower_password:
            raise serializers.ValidationError({"new_password": "No debe contener el nombre de usuario."})

        if email_local_lower and email_local_lower in lower_password:
            raise serializers.ValidationError({"new_password": "No debe contener partes del email."})

        common_passwords = {
            "12345678",
            "123456789",
            "password",
            "admin123",
            "qwerty123",
        }
        if lower_password in common_passwords:
            raise serializers.ValidationError({"new_password": "La contrasena es demasiado comun."})

        try:
            validate_password(password, user=user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"new_password": list(exc.messages)}) from exc

    def save(self, **kwargs):
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.must_change_password = False
        user.password_changed_at = timezone.now()
        user.save(update_fields=["password", "must_change_password", "password_changed_at", "updated_at"])
        return user


class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    default_error_messages = {
        "invalid_credentials": "Credenciales invalidas.",
    }

    def validate(self, attrs):
        identifier = attrs["identifier"].strip()
        password = attrs["password"]

        user = User.objects.filter(
            Q(username__iexact=identifier) | Q(email__iexact=identifier)
        ).first()
        if user is None:
            raise AuthenticationFailed(self.error_messages["invalid_credentials"])

        authenticated_user = authenticate(
            request=self.context.get("request"),
            username=user.username,
            password=password,
        )
        if authenticated_user is None or not authenticated_user.is_active:
            raise AuthenticationFailed(self.error_messages["invalid_credentials"])

        now = timezone.now()
        type(authenticated_user).objects.filter(pk=authenticated_user.pk).update(
            last_login=now,
            last_activity_at=now,
        )
        authenticated_user.last_login = now
        authenticated_user.last_activity_at = now

        refresh = RefreshToken.for_user(authenticated_user)
        refresh["username"] = authenticated_user.username
        refresh["email"] = authenticated_user.email

        user_payload = CurrentUserSerializer(
            authenticated_user,
            context=self.context,
        ).data

        return {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": user_payload,
        }


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()

    def save(self, **kwargs):
        try:
            token = RefreshToken(self.validated_data["refresh"])
            token.blacklist()
        except TokenError as exc:
            raise serializers.ValidationError({"refresh": "Token de refresh invalido o expirado."}) from exc
