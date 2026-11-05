from fastapi import status, HTTPException

from functools import wraps

from app.database.models import Role

def roles_required(*allowed_roles: Role):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            user = kwargs.get('current_user')

            if user is None:
                raise RuntimeError(
                    f"Endpoint '{func.__name__}' does not have param "
                    f"current_user = Depends(get_current_user)"
                )

            if user.role not in allowed_roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail='Insufficient rights'
                )

            return await func(*args, **kwargs)

        return wrapper

    return decorator
        