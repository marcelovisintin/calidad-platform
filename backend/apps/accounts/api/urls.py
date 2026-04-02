from django.urls import path

from apps.accounts.api.views import (
    AccountsApiRootAPIView,
    ChangePasswordAPIView,
    CurrentUserAPIView,
    LoginAPIView,
    LogoutAPIView,
    RefreshTokenAPIView,
    UserDetailAPIView,
    UserManagementAPIView,
)

app_name = "accounts"

urlpatterns = [
    path("", AccountsApiRootAPIView.as_view(), name="root"),
    path("login/", LoginAPIView.as_view(), name="login"),
    path("refresh/", RefreshTokenAPIView.as_view(), name="refresh"),
    path("logout/", LogoutAPIView.as_view(), name="logout"),
    path("change-password/", ChangePasswordAPIView.as_view(), name="change-password"),
    path("me/", CurrentUserAPIView.as_view(), name="me"),
    path("users/", UserManagementAPIView.as_view(), name="user-list"),
    path("users/<uuid:pk>/", UserDetailAPIView.as_view(), name="user-detail"),
]
