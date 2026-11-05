from pathlib import Path
import os
from dotenv import load_dotenv

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from jose import JWTError, jwt
from passlib.context import CryptContext

from sqlalchemy.orm import Session

from app.database.connect_to_db import db_connect
from app.database.models import User

from typing import Optional

from datetime import datetime, timedelta, timezone

BASE_DIR = Path(__file__).resolve().parent.parent
env_path = BASE_DIR / '.env'

load_dotenv(dotenv_path=env_path)

KEY = os.getenv('SECRET_KEY')
ALGORITHM = os.getenv('ALGORITHM')

oauth2_scheme = OAuth2PasswordBearer(tokenUrl='/api/users/login')

class Hash:
    pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')

    def verify_password(self, plain_password, hashed_password):
        return self.pwd_context.verify(plain_password, hashed_password)

    def get_password_hash(self, password: str):
        return self.pwd_context.hash(password)

async def create_access_token(data: dict, expires_delta: Optional[float] = None):
    encoded_data = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + timedelta(seconds=expires_delta)
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    
    encoded_data.update({
        'iat': datetime.now(timezone.utc),
        'exp': expire,
        'scope': 'access_token'
    })

    access_token = jwt.encode(encoded_data, KEY, algorithm=ALGORITHM)

    return access_token

async def create_refresh_token(data: dict, expires_delta: Optional[float] = None):
    encoded_data = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + timedelta(seconds=expires_delta)
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=7)

    encoded_data.update({
        'iat': datetime.now(timezone.utc),
        'exp': expire,
        'scope': 'refresh_token'
    })

    refresh_token = jwt.encode(encoded_data, KEY, algorithm=ALGORITHM)

    return refresh_token

async def create_email_token(data: dict):
    encoded_data = data.copy()

    expire = datetime.now(timezone.utc) + timedelta(days=7)

    encoded_data.update({
        'iat': datetime.now(timezone.utc),
        'exp': expire,
        'scope': 'email_token'
    })

    email_token = jwt.encode(encoded_data, KEY, algorithm=ALGORITHM)

    return email_token

async def get_email_from_token(token: str):
    try:
        payload = jwt.decode(token, KEY, algorithms=[ALGORITHM])
        if payload['scope'] == 'email_token':
            email = payload['sub']
            return email
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail='Invalid token type!'
            )
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail='Verification error!'
        )

async def get_email_from_refresh_token(refresh_token: str):
    try:
        payload = jwt.decode(refresh_token, KEY, algorithms=[ALGORITHM])

        if payload['scope'] == 'refresh_token':
            email = payload['sub']

            return email
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail='Invalid token type!'
            )
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Unauthorized user!'
        )

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(db_connect)):
    exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail='Unauthorized user!',
        headers={'WWW-Authenticate': 'Bearer'}
    )

    try:
        payload = jwt.decode(token, KEY, algorithms=[ALGORITHM])

        if payload['scope'] == 'access_token':
            email = payload['sub']

            if email is None:
                raise exception
        else:
            raise exception
    except JWTError as e:
        raise exception

    current_user = db.query(User).filter(User.email == email).first()

    if current_user is None:
        raise exception

    return current_user
