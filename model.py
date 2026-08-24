# model.py
from pydantic import BaseModel


class ShopItem(BaseModel):
    name: str
    description: str | None = None
    price: int
    tax: float | None = None


class ChatRequest(BaseModel):
    prompt: str


class ExtractRequest(BaseModel):
    text: str


class UserIn(BaseModel):
    username: str
    email: str
    password: str


class UserOut(BaseModel):
    # Same shape as UserIn minus the password: used as response_model so the
    # secret can never leak into a response, even if the code returns it.
    username: str
    email: str
