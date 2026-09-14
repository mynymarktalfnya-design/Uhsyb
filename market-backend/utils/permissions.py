"""Compatibility permission helpers for the current admin/manager/cashier roles.

The active API uses ``utils.deps``. These helpers remain for older integrations,
but deliberately share the current role names and do not define a second RBAC model.
"""
from functools import wraps
from fastapi import HTTPException, status

ROLE_PERMISSIONS = {
    "admin": {"view_all", "create_all", "edit_all", "delete_all", "view_profits", "manage_users", "manage_settings", "view_reports", "export_data"},
    "manager": {"view_all", "create_products", "edit_products", "create_sales", "view_customers", "create_customers", "edit_customers", "view_suppliers", "create_suppliers", "view_reports", "view_profits"},
    "cashier": {"view_products", "create_sales", "view_customers"},
}


def _role_value(role):
    return getattr(role, "value", role)


def check_permission(user_role: str, required_permission: str) -> bool:
    return required_permission in ROLE_PERMISSIONS.get(_role_value(user_role), set())


def require_permission(permission: str):
    """Compatibility decorator for handlers that expose ``request.state.user``."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request = kwargs.get("request")
            user = getattr(getattr(request, "state", None), "user", None) if request else None
            if not user:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="غير مصرح به")
            role = user.get("role") if isinstance(user, dict) else getattr(user, "role", None)
            if not check_permission(role, permission):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="ليس لديك صلاحية لهذه العملية")
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def require_roles(allowed_roles):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request = kwargs.get("request")
            user = getattr(getattr(request, "state", None), "user", None) if request else None
            if not user:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="غير مصرح به")
            role = user.get("role") if isinstance(user, dict) else getattr(user, "role", None)
            if _role_value(role) not in {_role_value(item) for item in allowed_roles}:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="ليس لديك صلاحية لهذه العملية")
            return await func(*args, **kwargs)
        return wrapper
    return decorator
