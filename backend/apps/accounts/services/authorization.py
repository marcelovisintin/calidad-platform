from apps.accounts.services.access_policy import is_management_user



def filter_user_directory_queryset(queryset, user):
    if not user or not user.is_authenticated:
        return queryset.none()
    if is_management_user(user):
        return queryset
    return queryset.filter(pk=user.pk)



def get_effective_permissions(user) -> list[str]:
    if not user or not user.is_authenticated:
        return []
    return sorted(user.get_all_permissions())
