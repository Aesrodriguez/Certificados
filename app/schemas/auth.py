from pydantic import BaseModel, EmailStr, Field


class LoginForm(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=255)
