from sqlalchemy.orm import Session

from app.database.models import Tag

def get_or_create_tags(names: list[str], db: Session) -> list[Tag]:
    if not names:
        return []

    existing_tags = db.query(Tag).filter(Tag.name.in_(names)).all()
    tags_by_name = {tag.name: tag for tag in existing_tags}

    for name in names:
        if name not in tags_by_name:
            new_tag = Tag(name=name)
            
            db.add(new_tag)

            tags_by_name[name] = new_tag

    db.flush()

    return [tags_by_name[name] for name in names]
