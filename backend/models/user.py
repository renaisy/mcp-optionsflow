"""
Pydantic models for user authentication
"""
from pydantic import BaseModel, EmailStr, validator
from datetime import datetime
from typing import Optional


class UserBase(BaseModel):
    """Base user model"""
    username: str
    email: EmailStr

    @validator('username')
    def username_alphanumeric(cls, v):
        if not v.replace('_', '').isalnum():
            raise ValueError('Username must be alphanumeric (underscores allowed)')
        if len(v) < 3 or len(v) > 50:
            raise ValueError('Username must be between 3 and 50 characters')
        return v


class UserCreate(UserBase):
    """User registration model"""
    password: str

    @validator('password')
    def password_strength(cls, v):
        if len(v) < 6:
            raise ValueError('Password must be at least 6 characters long')
        return v


class UserLogin(BaseModel):
    """User login model"""
    username: str
    password: str


class UserResponse(UserBase):
    """User response model"""
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    """JWT token response"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    """JWT token payload"""
    sub: Optional[str] = None  # user_id as string
    exp: Optional[int] = None
    type: Optional[str] = None  # 'access' or 'refresh'
