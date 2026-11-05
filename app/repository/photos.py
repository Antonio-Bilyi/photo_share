from sqlalchemy.orm import Session

from app.database.models import Photo, Tag


async def create_photo(user_id: int, description: str, url: str, public_id: str, tags: list[Tag], db: Session) -> Photo:
    photo = Photo(
        user_id=user_id,
        description=description,
        url=url,
        public_id=public_id,
        tags=tags
    )

    db.add(photo)
    db.commit()
    db.refresh(photo)

    return photo

async def get_photo(photo_id: int, db: Session) -> Photo | None:
    photo = db.query(Photo).filter(Photo.id == photo_id).first()

    return photo

async def update_description(photo: Photo, description: str, db: Session):
    photo.description = description

    db.commit()
    db.refresh(photo)

    return photo


async def delete_photo(photo: Photo, db: Session):
    db.delete(photo)
    db.commit()