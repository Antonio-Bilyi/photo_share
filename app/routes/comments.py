from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.authorize import get_current_user
from app.database.connect_to_db import db_connect
from app.database.models import Role, User
from app.schemas import CommentCreate, CommentResponse, CommentUpdate

import app.repository.photos as repository_photo
import app.repository.comments as repository_comment
from app.services.comment_access import check_comment_author
from app.services.roles import roles_required

router = APIRouter(prefix='/photos/{photo_id}/comments', tags=['comments'])

@router.post('/', response_model=CommentResponse, status_code=201)
async def create_comment(photo_id: int, body: CommentCreate, current_user: User = Depends(get_current_user), db: Session = Depends(db_connect)):
    photo = await repository_photo.get_photo(photo_id, db)
    if photo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Photo not found'
        )

    return await repository_comment.create_comment(current_user.id, photo_id, body.text, db)

@router.get('/', response_model=list[CommentResponse])
async def get_comments(photo_id: int, skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100), current_user: User = Depends(get_current_user), db: Session = Depends(db_connect)):
    photo = await repository_photo.get_photo(photo_id, db)
    if photo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Photo not found'
            )
    
    return await repository_comment.get_comments(photo_id, skip, limit, db)

@router.put('/{comment_id}', response_model=CommentResponse)
async def update_comment(photo_id: int, comment_id: int, body: CommentUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(db_connect)):
    comment = await repository_comment.get_comment(photo_id, comment_id, db)
    
    check_comment_author(comment, current_user)

    return await repository_comment.update_comment(comment, body.text, db)

@router.delete('/{comment_id}', status_code=204)
@roles_required(Role.ADMIN, Role.MODERATOR)
async def delete_comment(photo_id: int, comment_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(db_connect)):
    comment = await repository_comment.get_comment(photo_id, comment_id, db)
    if comment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Comment not found'
            )

    await repository_comment.delete_comment(comment, db)

    return Response(status_code=status.HTTP_204_NO_CONTENT)