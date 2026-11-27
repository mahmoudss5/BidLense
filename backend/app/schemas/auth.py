from pydantic import BaseModel, EmailStr, Field





class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
