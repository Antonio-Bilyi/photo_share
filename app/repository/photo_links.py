from sqlalchemy.orm import Session

from app.database.models import PhotoLink


async def create_link(photo_id: int, url: str, params: dict, db: Session) -> PhotoLink:
    photo_link = PhotoLink(
        photo_id=photo_id,
        url=url,
        params=params
    )

    db.add(photo_link)
    db.commit()
    db.refresh(photo_link)

    return photo_link

async def get_link(photo_id: int, link_id: int, db: Session) -> PhotoLink | None:
    photo_link = db.query(PhotoLink).filter(PhotoLink.id == link_id, PhotoLink.photo_id == photo_id).first()
    
    return photo_link

async def get_links(photo_id: int, db: Session) -> list[PhotoLink]:
    photo_links = db.query(PhotoLink).filter(PhotoLink.photo_id == photo_id).order_by(PhotoLink.created_at.desc()).all()

    return photo_links

