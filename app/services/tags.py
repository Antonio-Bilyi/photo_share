import re

from fastapi import HTTPException, status

MAX_TAGS = 5
MAX_TAG_LENGTH = 25
TAG_PATTERN = re.compile(r'[\w-]+')

def parse_tags(raw: str | None) -> list[str]:
    if not raw:
        return []

    tags = [tag.strip().lstrip('#').strip().lower() for tag in raw.split(',')]
    tags = [tag for tag in tags if tag]
    tags = list(dict.fromkeys(tags))

    if len(tags) > MAX_TAGS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'Maximum {MAX_TAGS} tags allowed'
        )

    for tag in tags:
        if len(tag) > MAX_TAG_LENGTH:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tag '{tag}' is too long (max {MAX_TAG_LENGTH} characters)"
            )

        if not TAG_PATTERN.fullmatch(tag):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tag '{tag}' contains invalid characters"
            )

    return tags
    