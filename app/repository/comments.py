from sqlalchemy.orm import Session

from app.database.models import Comment


async def create_comment(user_id: int, photo_id: int, text: str, db: Session) -> Comment:
    comment = Comment(
        user_id=user_id,
        photo_id=photo_id,
        text=text
    )

    db.add(comment)
    db.commit()
    db.refresh(comment)

    return comment

async def get_comment(photo_id: int, comment_id: int, db: Session) -> Comment | None:
    comment = db.query(Comment).filter(Comment.id == comment_id, Comment.photo_id == photo_id).first()
    
    return comment

async def get_comments(photo_id: int, skip: int, limit: int, db: Session) -> list[Comment]:
    comments = db.query(Comment).filter(Comment.photo_id == photo_id).order_by(Comment.created_at.asc()).offset(skip).limit(limit).all()

    return comments

async def update_comment(comment: Comment, text: str, db: Session) -> Comment:
    comment.text = text

    db.commit()
    db.refresh(comment)

    return comment

async def delete_comment(comment: Comment, db: Session) -> None:
    db.delete(comment)
    db.commit()