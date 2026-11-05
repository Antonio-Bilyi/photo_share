from fastapi import HTTPException, UploadFile, status

from PIL import Image, UnidentifiedImageError

ALLOWED_TYPES = {'image/jpeg', 'image/png', 'image/webp'}
ALLOWED_FORMATS = {'JPEG', 'PNG', 'WEBP'}
MAX_SIZE = 5 * 1024 * 1024

def validate_image(file: UploadFile):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail='Only JPEG, PNG and WEBP images are allowed'
        )

    file.file.seek(0, 2)
    size = file.file.tell()
    file.file.seek(0)

    if size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='File is empty'
        )

    if size > MAX_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f'File is too large (max {MAX_SIZE // (1024 * 1024)} MB)'
        )

    try:
        with Image.open(file.file) as img:
            if img.format not in ALLOWED_FORMATS:
                raise HTTPException(
                    status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                    detail='Only JPEG, PNG and WEBP images are allowed'
                )

            img.verify()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Invalid image file'
        ) from err
    finally:
        file.file.seek(0)