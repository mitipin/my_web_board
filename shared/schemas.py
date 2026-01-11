"""
Pydantic схемы для валидации данных
"""
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional
from datetime import datetime
from enum import Enum


class TaskStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


# User schemas
class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    full_name: Optional[str] = None


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)


class UserLogin(BaseModel):
    username: str
    password: str


class UserResponse(UserBase):
    id: int
    balance: float
    rating: float
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Task schemas
class TaskBase(BaseModel):
    title: str = Field(..., min_length=5, max_length=200)
    description: Optional[str] = None
    price: float = Field(..., gt=0)
    category: Optional[str] = None
    deadline: Optional[datetime] = None


class TaskCreate(TaskBase):
    pass


class TaskResponse(TaskBase):
    id: int
    status: TaskStatus
    creator_id: int
    executor_id: Optional[int]
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


# Chat schemas
class ChatMessageBase(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)


class ChatMessageCreate(ChatMessageBase):
    task_id: int


class ChatMessageResponse(ChatMessageBase):
    id: int
    task_id: int
    sender_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Token schemas
class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None
