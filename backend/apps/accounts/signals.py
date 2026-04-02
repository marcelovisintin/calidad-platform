from django.db.models.signals import post_migrate

from apps.accounts.services.role_setup import sync_roles_and_permissions



def bootstrap_accounts_security(sender, app_config, **kwargs) -> None:
    if app_config.label != "accounts":
        return
    sync_roles_and_permissions()


post_migrate.connect(
    bootstrap_accounts_security,
    dispatch_uid="accounts.bootstrap_accounts_security",
)
