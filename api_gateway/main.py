"""
API Gateway - единая точка входа
"""
import json
import urllib
from api_gateway.handlers import handle_register, handle_login
from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx
import logging
import sys
from pathlib import Path
from datetime import datetime

# Добавляем корневую директорию в путь Python
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.security import verify_token

# Импортируем схемы
from api_gateway.schemas import UserCreate, UserLogin, Token, TaskCreate, ChatMessageCreate

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Quest Board API Gateway",
    description="Единая точка входа для всех микросервисов квест-доски",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {
            "name": "Auth",
            "description": "Аутентификация и регистрация пользователей",
        },
        {
            "name": "Quests",
            "description": "Управление заданиями (квестами)",
        },
        {
            "name": "Chat",
            "description": "Общение по заданиям",
        },
        {
            "name": "Notifications",
            "description": "Уведомления",
        },
        {
            "name": "Health",
            "description": "Проверка здоровья сервисов",
        },
    ]
)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене указать конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# URL микросервисов
SERVICE_URLS = {
    "auth": "http://localhost:8001",
    "quest": "http://localhost:8002",
    "chat": "http://localhost:8003",
    "notification": "http://localhost:8004",
}

# Публичные endpoints (не требуют аутентификации)
PUBLIC_ENDPOINTS = [
    "/",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/health",
    "/services/health",
    "/auth/register",
    "/auth/login",
    "/auth/health",
    "/quest/health",
    "/chat/health",
    "/notification/health",
]


async def forward_request(
        request: Request,
        service_url: str,
        path: str
) -> JSONResponse:
    """
    Перенаправление запроса на микросервис
    """
    try:
        # Подготавливаем URL
        url = f"{service_url}{path}"

        # Подготавливаем заголовки
        headers = dict(request.headers)
        headers.pop("host", None)

        # Получаем тело запроса
        body = await request.body()

        # Отправляем запрос
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(
                method=request.method,
                url=url,
                headers=headers,
                content=body,
                params=dict(request.query_params)
            )

            # Возвращаем ответ
            return JSONResponse(
                content=response.json() if response.content else {},
                status_code=response.status_code,
                headers=dict(response.headers)
            )

    except httpx.TimeoutException:
        logger.error(f"Таймаут при обращении к {service_url}{path}")
        return JSONResponse(
            status_code=504,
            content={"detail": "Сервис временно недоступен"}
        )
    except httpx.RequestError as e:
        logger.error(f"Ошибка при обращении к {service_url}{path}: {e}")
        return JSONResponse(
            status_code=502,
            content={"detail": "Ошибка подключения к сервису"}
        )
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": "Внутренняя ошибка сервера"}
        )


@app.middleware("http")
async def gateway_middleware(request: Request, call_next):
    """
    Middleware для маршрутизации и аутентификации
    """
    # Определяем путь
    path = request.url.path

    # Пропускаем публичные endpoints
    if path in PUBLIC_ENDPOINTS or path.startswith("/docs") or path.startswith("/redoc"):
        return await call_next(request)

    # Определяем сервис по пути
    service = None
    service_path = path

    if path.startswith("/auth/"):
        service = "auth"
        service_path = path.replace("/auth", "", 1)
    elif path.startswith("/quest/"):
        service = "quest"
        service_path = path.replace("/quest", "", 1)
    elif path.startswith("/chat/"):
        service = "chat"
        service_path = path.replace("/chat", "", 1)
    elif path.startswith("/notification/"):
        service = "notification"
        service_path = path.replace("/notification", "", 1)
    else:
        # Неизвестный путь
        return JSONResponse(
            status_code=404,
            content={"detail": "Эндпоинт не найден"}
        )

    # Проверяем аутентификацию (кроме публичных endpoints)
    auth_header = request.headers.get("Authorization")

    if not auth_header or not auth_header.startswith("Bearer "):
        return JSONResponse(
            status_code=401,
            content={"detail": "Требуется аутентификация"}
        )

    # Проверяем токен
    token = auth_header.split("Bearer ")[1]
    payload = verify_token(token)

    if not payload:
        return JSONResponse(
            status_code=401,
            content={"detail": "Неверный токен"}
        )

    # Перенаправляем запрос
    service_url = SERVICE_URLS.get(service)
    if not service_url:
        return JSONResponse(
            status_code=502,
            content={"detail": f"Сервис {service} недоступен"}
        )

    return await forward_request(request, service_url, service_path)


@app.post("/auth/register", response_model=dict, tags=["Auth"])
async def register_user(user_data: UserCreate):
    """
    Регистрация нового пользователя
    """
    return await handle_register(user_data)


@app.post("/auth/login", response_model=Token, tags=["Auth"])
async def login_user(login_data: UserLogin):
    """
    Вход в систему
    """
    return await handle_login(login_data)


@app.post("/quest/tasks", response_model=dict, tags=["Quests"])
async def create_task(task_data: TaskCreate):
    """
    Создание нового задания

    - **title**: Название задания (5-200 символов)
    - **description**: Описание задания
    - **price**: Цена задания (> 0)
    - **category**: Категория задания
    - **deadline**: Срок выполнения (опционально)
    """
    return {"message": "Используйте этот эндпоинт для создания задания. Запрос будет перенаправлен в quest_service."}


@app.post("/chat/messages", response_model=dict, tags=["Chat"])
async def send_message(message_data: ChatMessageCreate):
    """
    Отправка сообщения в чат

    - **task_id**: ID задания
    - **message**: Текст сообщения (1-2000 символов)
    """
    return {"message": "Используйте этот эндпоинт для отправки сообщения. Запрос будет перенаправлен в chat_service."}


# Прокси endpoints (для реальной работы)
@app.api_route("/auth/{path:path}", methods=["GET", "POST", "PUT", "DELETE"], include_in_schema=False)
async def auth_proxy(request: Request, path: str):
    """Прокси для auth сервиса (скрыто из документации)"""
    return await forward_request(request, SERVICE_URLS["auth"], f"/{path}")


@app.api_route("/quest/{path:path}", methods=["GET", "POST", "PUT", "DELETE"], include_in_schema=False)
async def quest_proxy(request: Request, path: str):
    """Прокси для quest сервиса (скрыто из документации)"""
    return await forward_request(request, SERVICE_URLS["quest"], f"/{path}")


@app.api_route("/chat/{path:path}", methods=["GET", "POST", "PUT", "DELETE"], include_in_schema=False)
async def chat_proxy(request: Request, path: str):
    """Прокси для chat сервиса (скрыто из документации)"""
    return await forward_request(request, SERVICE_URLS["chat"], f"/{path}")


@app.api_route("/notification/{path:path}", methods=["GET", "POST", "PUT", "DELETE"], include_in_schema=False)
async def notification_proxy(request: Request, path: str):
    """Прокси для notification сервиса (скрыто из документации)"""
    return await forward_request(request, SERVICE_URLS["notification"], f"/{path}")


# Health checks
@app.get("/", tags=["Health"])
async def root():
    """
    Корневой endpoint API Gateway
    """
    return {
        "service": "api-gateway",
        "version": "1.0.0",
        "description": "API Gateway для квест-доски",
        "endpoints": {
            "auth": {
                "register": "/auth/register",
                "login": "/auth/login",
                "me": "/auth/me",
                "direct_docs": "http://localhost:8001/docs"
            },
            "quest": {
                "tasks": "/quest/tasks",
                "direct_docs": "http://localhost:8002/docs"
            },
            "chat": {
                "messages": "/chat/messages",
                "direct_docs": "http://localhost:8003/docs"
            },
            "notification": {
                "notifications": "/notification/notifications",
                "direct_docs": "http://localhost:8004/docs"
            }
        },
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/health", tags=["Health"])
async def health():
    """
    Проверка здоровья API Gateway
    """
    return {
        "status": "healthy",
        "service": "api-gateway",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/services/health", tags=["Health"])
async def services_health():
    """
    Проверка здоровья всех микросервисов
    """
    health_status = {}

    async with httpx.AsyncClient(timeout=5.0) as client:
        for service_name, service_url in SERVICE_URLS.items():
            try:
                response = await client.get(f"{service_url}/health")
                health_status[service_name] = {
                    "status": "healthy" if response.status_code == 200 else "unhealthy",
                    "status_code": response.status_code,
                    "url": service_url
                }
            except Exception as e:
                health_status[service_name] = {
                    "status": "unreachable",
                    "error": str(e),
                    "url": service_url
                }

    all_healthy = all(
        status["status"] == "healthy"
        for status in health_status.values()
    )

    return {
        "gateway": "healthy",
        "all_services_healthy": all_healthy,
        "services": health_status,
        "timestamp": datetime.utcnow().isoformat()
    }


if __name__ == "__main__":
    import uvicorn

    print("=" * 60)
    print("Запуск API Gateway для квест-доски")
    print("=" * 60)
    print(f"Время запуска: {datetime.now()}")
    print(f"API Gateway: http://localhost:8000")
    print(f"Документация: http://localhost:8000/docs")
    print("\nМикросервисы:")
    for service, url in SERVICE_URLS.items():
        print(f"  {service}: {url}")
    print("=" * 60)

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )