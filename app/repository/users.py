from sqlalchemy.orm import Session

from fastapi import HTTPException, status, BackgroundTasks, Request
from fastapi.security import OAuth2PasswordRequestForm, HTTPAuthorizationCredentials

from app.schemas import UserModel, RequestEmail
from app.database.models import User, Role
from app.authorize import create_access_token, create_refresh_token, get_email_from_refresh_token, Hash, get_email_from_token
from app.services.send_email import send_email

hash_handler = Hash()

async def create_user(body: UserModel, background_tasks: BackgroundTasks, request: Request, db: Session):
    exist_username = db.query(User).filter(User.username == body.username).first()
    if exist_username:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='Username already exists'
        )

    exist_email = db.query(User).filter(User.email == body.email).first()
    if exist_email:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='Email already exists'
        )

    data = body.model_dump()
    data['password'] = hash_handler.get_password_hash(body.password)

    has_user = db.query(User.id).first() is not None
    role = Role.USER if has_user else Role.ADMIN

    new_user = User(**data, role=role)

    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    background_tasks.add_task(send_email, new_user.email, body.username, str(request.base_url))

    return {
        'user': new_user,
        'detail': 'User successfully created! Please, check your email for confirmation.'
    }

async def get_user(body: OAuth2PasswordRequestForm, db: Session):
    user = db.query(User).filter(User.username == body.username).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='User not found!'
        )

    if not hash_handler.verify_password(body.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='User not found!'
        )
    
    if not user.confirmed:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Email not confirmed!'
        )

    access_token = await create_access_token(data={'sub': user.email})
    refresh_token = await create_refresh_token(data={'sub': user.email})

    user.refresh_token = refresh_token

    db.commit()

    return {
        'access_token': access_token,
        'refresh_token': refresh_token,
        'token_type': 'bearer'  
    }

async def get_refresh_token(credentials: HTTPAuthorizationCredentials, db: Session):
    token = credentials.credentials

    email = await get_email_from_refresh_token(token)

    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='User not found!'
        )

    if user.refresh_token != token:
        user.refresh_token = None

        db.commit()

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Invalid refresh_token'
        )

    access_token = await create_access_token(data={'sub': user.email})
    refresh_token = await create_refresh_token(data={'sub': user.email})
    
    user.refresh_token = refresh_token
    
    db.commit()
    
    return {
        'access_token': access_token,
        'refresh_token': refresh_token,
        'token_type': 'bearer'  
    }

async def confirm_email(token: str, db: Session):
    email = await get_email_from_token(token)

    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Verification error'
        )

    if user.confirmed:
        return {'message': 'Your email is already confirmed'}
    
    user.confirmed = True
    db.commit()

    return {'message': 'Email successfully confirmed'}

async def request_email(body: RequestEmail, background_tasks: BackgroundTasks, request: Request, db: Session):
    user = db.query(User).filter(User.email == body.email).first()
    if user and not user.confirmed:
        background_tasks.add_task(send_email, user.email, user.username, str(request.base_url))

    return {'message': 'Check your email for confirmation'}