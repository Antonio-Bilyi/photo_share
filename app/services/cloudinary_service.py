import os
from pathlib import Path
from dotenv import load_dotenv

import cloudinary
import cloudinary.uploader
from cloudinary.exceptions import Error as CloudinaryError

from uuid import uuid4

from fastapi import HTTPException, status

import logging

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
env_path = BASE_DIR / '.env'
load_dotenv(dotenv_path=env_path)

cloudinary.config(
    cloud_name = os.getenv('CLOUD_NAME'),
    api_key = os.getenv('CLOUD_KEY'),
    api_secret = os.getenv('CLOUD_SECRET'),
    secure = True
)

def upload(user_id: int, file):
    public_id = f'PhotoShare/{user_id}/{uuid4().hex}'

    file.seek(0)

    try:
        result = cloudinary.uploader.upload(file, public_id=public_id)
    except CloudinaryError as err:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail='Failed to upload image'
        ) from err

    return result['secure_url'], result['public_id']

def delete(public_id: str):
    try:
        result = cloudinary.uploader.destroy(public_id)
    except CloudinaryError as err:
        logger.error('Cloudinary delete failed for %s: %s', public_id, err)

        return False

    if result.get('result') !='ok':
        logger.warning('Cloudinary did not delete %s: %s', public_id, result)

        return False

    return True

def transform(public_id: str, params: dict):
    return cloudinary.CloudinaryImage(public_id).build_url(**params)