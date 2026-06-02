from pydantic import BaseModel


class RegisterRequest(BaseModel):
    username: str
    password: str
    bio: str | None = None
    school: str | None = None


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserResponse"


from app.schemas.user import UserResponse
