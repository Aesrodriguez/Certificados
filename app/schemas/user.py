from pydantic import BaseModel, EmailStr, Field

from app.models.user import RoleEnum


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=10, max_length=255)
    role: RoleEnum


class UserRoleUpdate(BaseModel):
    role: RoleEnum
