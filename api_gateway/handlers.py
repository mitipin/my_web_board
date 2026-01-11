"""
Обработчики для API Gateway
"""
from fastapi import Request
import httpx
import json
import urllib.parse
from api_gateway.schemas import UserCreate, UserLogin
from api_gateway.main import SERVICE_URLS


async def handle_register(user_data: UserCreate):
    """Регистрация пользователя"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{SERVICE_URLS['auth']}/register",
            json=user_data.dict(),
            headers={"Content-Type": "application/json"}
        )
        return response.json()


async def handle_login(login_data: UserLogin):
    """Вход пользователя"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{SERVICE_URLS['auth']}/login",
            data={
                "username": login_data.username,
                "password": login_data.password
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        return response.json()