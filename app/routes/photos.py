import base64

from fastapi import APIRouter, Depends, File, Form, UploadFile, Response, HTTPException, status

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.authorize import get_current_user
from app.database.connect_to_db import db_connect
from app.database.models import User
from app.schemas import PhotoResponse, PhotoUpdate, TransformationParams, PhotoLinkCreateResponse, PhotoLinkResponse
from app.services.files import validate_image
import app.services.tags as tags_services
import app.services.cloudinary_service as cloudinary_services
import app.services.qr as qr_services
import app.repository.tags as repository_tags
import app.repository.photos as repository_photos
import app.repository.photo_links as repository_photo_links
from app.services.photo_access import check_photo_access

router = APIRouter(prefix='/photos', tags=['photos'])

@router.post('/', response_model=PhotoResponse, status_code=201)
async def create_photo(file: UploadFile = File(), description: str = Form(min_length=1, max_length=255), tags: str | None = Form(None), current_user: User = Depends(get_current_user), db: Session = Depends(db_connect)):
    tag_names = tags_services.parse_tags(tags)

    validate_image(file)

    url, public_id = cloudinary_services.upload(current_user.id, file.file)

    try: 
        tag_objects = repository_tags.get_or_create_tags(tag_names, db)

        photo = await repository_photos.create_photo(
            current_user.id,
            description,
            url,
            public_id,
            tag_objects,
            db
        )
    except SQLAlchemyError as err:
        db.rollback()

        cloudinary_services.delete(public_id)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Failed to save photo'
        ) from err

    return photo

@router.get('/{photo_id}', response_model=PhotoResponse)
async def read_photo(photo_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(db_connect)):
    photo = await repository_photos.get_photo(photo_id, db)
    if photo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Photo not found'
        )

    return photo

@router.put('/{photo_id}', response_model=PhotoResponse)
async def update_photo(body: PhotoUpdate, photo_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(db_connect)):
    photo = await repository_photos.get_photo(photo_id, db)

    check_photo_access(photo, current_user)

    updated_photo = await repository_photos.update_description(photo, body.description, db)

    return updated_photo

@router.delete('/{photo_id}', status_code=204)
async def delete_photo(photo_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(db_connect)):
    photo = await repository_photos.get_photo(photo_id, db)

    check_photo_access(photo, current_user)

    public_id = photo.public_id

    await repository_photos.delete_photo(photo, db)

    cloudinary_services.delete(public_id)

    return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.post('/{photo_id}/links', response_model=PhotoLinkCreateResponse, status_code=201)
async def create_photo_link(body: TransformationParams, photo_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(db_connect)):
    photo = await repository_photos.get_photo(photo_id, db)

    check_photo_access(photo, current_user)

    params = body.model_dump(mode='json', exclude_none=True)

    url = cloudinary_services.transform(photo.public_id, params)

    link = await repository_photo_links.create_link(photo.id, url, params, db)

    png = qr_services.generate_qr(link.url)

    qr_decode = base64.b64encode(png).decode()

    return {
        'link': link,
        'qr_code': qr_decode
    }

@router.get('/{photo_id}/links/{link_id}/qr', response_class=Response)
async def get_qr_from_link(photo_id: int, link_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(db_connect)):
    link = await repository_photo_links.get_link(photo_id, link_id, db)
    if link is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Link not found'
        )

    png = qr_services.generate_qr(link.url)

    return Response(content=png, media_type='image/png')

@router.get('/{photo_id}/links', response_model=list[PhotoLinkResponse])
async def get_photo_links(photo_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(db_connect)):
    photo = await repository_photos.get_photo(photo_id, db)
    if photo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Photo not found'
        )

    return await repository_photo_links.get_links(photo_id, db)

    



    




    
