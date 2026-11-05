from fastapi import HTTPException, status

from app.database.models import Comment, User


def check_comment_author(comment: Comment | None, current_user: User) -> Comment:
    if comment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Comment not found!'
        )

    if comment.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Forbidden!'
        )

    return comment