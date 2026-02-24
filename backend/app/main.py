import os

import httpx
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import engine, Base, get_db
from app.models import User
from app.auth import hash_password, verify_password, create_access_token
from app.dependencies import get_current_user

from fastapi.staticfiles import StaticFiles

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
# ---------- schemas ----------

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------- routes ----------

@app.post("/register", response_model=TokenResponse, status_code=201)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.scalar(select(User).where(User.email == body.email))
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(email=body.email, hashed_password=hash_password(body.password))
    db.add(user)
    await db.commit()

    token = create_access_token(str(user.id))
    return TokenResponse(access_token=token)


@app.post("/login", response_model=TokenResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    user = await db.scalar(select(User).where(User.email == form_data.username))
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(str(user.id))
    return TokenResponse(access_token=token)


@app.get("/me")
async def me(current_user: User = Depends(get_current_user)):
    return {"id": current_user.id, "email": current_user.email}


# ---------- telnyx webhooks ----------

@app.post("/webhooks/telnyx", status_code=200)
async def telnyx_webhook(request: Request):
    body = await request.json()
    event_type = body.get("data", {}).get("event_type")

    print("body")

    if event_type == "call.answered":
        call_control_id = body["data"]["payload"]["call_control_id"]
        api_key = os.environ["TELNYX_API_KEY"]

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://api.telnyx.com/v2/calls/{call_control_id}/actions/playback_start",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"audio_url": "https://uncabled-zina-fusilly.ngrok-free.dev/static/test.mp3"},
            )
            response.raise_for_status()

    return {"status": "ok"}

