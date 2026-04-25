from django.db.models import Q

from apps.accounts.constants import ROLE_ADMINISTRADOR


def get_user_role_codes(user) -> list[str]:
    if not user or not user.is_authenticated:
        return []

    codes = set(user.role_scopes.values_list("role__code", flat=True).distinct())
    if user.is_superuser:
        codes.add(ROLE_ADMINISTRADOR)
    return sorted(code for code in codes if code)



def get_user_accessible_site_ids(user) -> set:
    if not user or not user.is_authenticated:
        return set()
    if user.is_superuser:
        return set()
    return set(
        user.role_scopes.filter(area__isnull=True).values_list("site_id", flat=True).distinct()
    )



def get_user_accessible_area_ids(user) -> set:
    if not user or not user.is_authenticated:
        return set()
    if user.is_superuser:
        return set()

    area_ids = set(
        user.role_scopes.filter(area__isnull=False).values_list("area_id", flat=True).distinct()
    )
    if user.primary_sector_id:
        area_ids.add(user.primary_sector_id)
    return area_ids



def can_access_area(user, area_id=None, site_id=None) -> bool:
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if getattr(user, "access_level", "") in {"administrador", "desarrollador"}:
        return True

    accessible_area_ids = get_user_accessible_area_ids(user)
    if area_id and area_id in accessible_area_ids:
        return True

    accessible_site_ids = get_user_accessible_site_ids(user)
    if site_id and site_id in accessible_site_ids:
        return True

    return False



def filter_queryset_by_sector_scope(queryset, user, area_field="area_id", site_field="site_id"):
    if not user or not user.is_authenticated:
        return queryset.none()
    if user.is_superuser:
        return queryset

    accessible_site_ids = get_user_accessible_site_ids(user)
    accessible_area_ids = get_user_accessible_area_ids(user)

    scoped_filter = Q()
    if accessible_site_ids and site_field:
        scoped_filter |= Q(**{f"{site_field}__in": list(accessible_site_ids)})
    if accessible_area_ids and area_field:
        scoped_filter |= Q(**{f"{area_field}__in": list(accessible_area_ids)})

    if not scoped_filter.children:
        return queryset.none()

    return queryset.filter(scoped_filter)



def filter_user_directory_queryset(queryset, user):
    if not user or not user.is_authenticated:
        return queryset.none()
    if user.is_superuser:
        return queryset

    accessible_site_ids = get_user_accessible_site_ids(user)
    accessible_area_ids = get_user_accessible_area_ids(user)

    scoped_filter = Q(pk=user.pk)
    if accessible_site_ids:
        scoped_filter |= Q(primary_sector__site_id__in=list(accessible_site_ids))
    if accessible_area_ids:
        scoped_filter |= Q(primary_sector_id__in=list(accessible_area_ids))

    return queryset.filter(scoped_filter).distinct()



def get_effective_permissions(user) -> list[str]:
    if not user or not user.is_authenticated:
        return []
    return sorted(user.get_all_permissions())
