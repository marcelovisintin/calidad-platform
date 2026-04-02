import re

from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.tokens import RefreshToken, TokenError

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
    class Meta:
        model = Role
        fields = ("id", "code", "name")


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
