from pydantic import BaseModel, Field, EmailStr, ConfigDict, model_validator

from datetime import datetime

from typing import Literal, Optional

from enum import Enum

from app.database.models import Role

class UserModel(BaseModel):
    username: str = Field(min_length=2, max_length=25)
    email: EmailStr = Field(max_length=150)
    password: str = Field(min_length=6, max_length=150)

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: Role
    confirmed: bool

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )

class SignUpResponse(BaseModel):
    user: UserResponse
    detail: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = 'bearer'

class RequestEmail(BaseModel):
    email: EmailStr

class TagResponse(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)

class PhotoResponse(BaseModel):
    id: int
    url: str
    description: str
    created_at: datetime
    updated_at: datetime
    user_id: int
    tags: list[TagResponse]

    model_config = ConfigDict(from_attributes=True)

class PhotoUpdate(BaseModel):
    description: str = Field(min_length=1, max_length=255)

class CropMode(str, Enum):
    FILL = 'fill'
    FIT = 'fit'
    SCALE = 'scale'
    THUMB = 'thumb'

class Effect(str, Enum):
    GRAYSCALE = 'grayscale'
    SEPIA = 'sepia'
    BLUR = 'blur:300'

class TransformationParams(BaseModel):
    width: Optional[int] = Field(default=None, ge=1, le=2000)
    height: Optional[int] = Field(default=None, ge=1, le=2000)
    crop: Optional[CropMode] = None
    angle: Optional[Literal[90, 180, 270]] = None
    effect: Optional[Effect] = None
    radius: Optional[int] = Field(default=None, ge=1, le=500)

    model_config = ConfigDict(extra='forbid')

    @model_validator(mode='after')
    def check_params(self):
        main_params = (self.width, self.height, self.angle, self.effect, self.radius)
        if all(param is None for param in main_params):
            raise ValueError('At least one transformation parameter is required')

        if self.crop is not None:
            if self.width is None and self.height is None:
                raise ValueError('Crop mode requires width or height')

            if self.crop in (CropMode.FILL, CropMode.THUMB) and (self.width is None or self.height is None):
                raise ValueError('Modes fill and thumb require both width and height')

        return self

class PhotoLinkResponse(BaseModel):
    id: int
    photo_id: int
    url: str
    params: dict
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class PhotoLinkCreateResponse(BaseModel):
    link: PhotoLinkResponse
    qr_code: str

class CommentCreate(BaseModel):
    text: str = Field(min_length=1, max_length=500)

    model_config = ConfigDict(str_strip_whitespace=True)

class CommentUpdate(BaseModel):
    text: str = Field(min_length=1, max_length=500)

    model_config = ConfigDict(str_strip_whitespace=True)

class CommentResponse(BaseModel):
    id: int
    text: str
    photo_id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


