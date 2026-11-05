from app.database.models import Photo, User, Role

from fastapi import HTTPException, status


def check_photo_access(photo: Photo, current_user: User):
    if photo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Photo not found'
        )
    
    if photo.user_id != current_user.id and current_user.role != Role.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Access denied'
        )

    return photo