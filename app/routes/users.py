from fastapi import APIRouter, BackgroundTasks, Depends, Request, Security
from fastapi.security import OAuth2PasswordRequestForm, HTTPAuthorizationCredentials, HTTPBearer

from app.schemas import UserModel, UserResponse, TokenResponse, SignUpResponse
from app.database.connect_to_db import db_connect
from app.database.models import User, Role
from app.authorize import get_current_user
from app.repository import users as repository_users
from app.services.roles import roles_required

from sqlalchemy.orm import Session


router = APIRouter(prefix='/users', tags=['users'])

security = HTTPBearer()

@router.post('/signup', response_model=SignUpResponse, status_code=201)
async def sign_up(body: UserModel, background_tasks: BackgroundTasks, request: Request, db: Session = Depends(db_connect)):
    return await repository_users.create_user(body, background_tasks, request, db)

@router.post('/login', response_model=TokenResponse)
async def login(body: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(db_connect)):
    return await repository_users.get_user(body, db)

@router.get('/me', response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user

@router.post('/refresh_token', response_model=TokenResponse)
async def refresh_token(credentials: HTTPAuthorizationCredentials = Security(security), db: Session = Depends(db_connect)):
    return await repository_users.get_refresh_token(credentials, db)

@router.get('/admin')
@roles_required(Role.ADMIN)
async def admin_only(current_user: User = Depends(get_current_user)):
    return {'message': f'Hello, admin {current_user.username}'}

@router.get('/moderator')
@roles_required(Role.MODERATOR)
async def moderator_only(current_user: User = Depends(get_current_user)):
    return {'message': f'Hello, moderator {current_user.username}'}

@router.get('/confirmed_email/{token}')
async def confirmed_email(token: str, db: Session = Depends(db_connect)):
    return await repository_users.confirm_email(token, db)