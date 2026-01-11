"""
Документация API для Gateway
"""
from fastapi.openapi.utils import get_openapi
from api_gateway.main import app


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title="Quest Board API Gateway",
        version="1.0.0",
        description="Единая точка входа для всех микросервисов квест-доски",
        routes=app.routes,
    )

    # Добавляем схемы для авторизации
    openapi_schema["paths"]["/auth/register"] = {
        "post": {
            "summary": "Регистрация пользователя",
            "description": "Создание нового пользователя",
            "tags": ["Auth"],
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {
                            "$ref": "#/components/schemas/UserCreate"
                        }
                    }
                }
            },
            "responses": {
                "201": {
                    "description": "Пользователь создан",
                    "content": {
                        "application/json": {
                            "schema": {
                                "$ref": "#/components/schemas/UserResponse"
                            }
                        }
                    }
                },
                "400": {
                    "description": "Ошибка регистрации"
                }
            }
        }
    }

    openapi_schema["paths"]["/auth/login"] = {
        "post": {
            "summary": "Вход в систему",
            "description": "Аутентификация пользователя",
            "tags": ["Auth"],
            "requestBody": {
                "required": True,
                "content": {
                    "application/x-www-form-urlencoded": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "username": {"type": "string"},
                                "password": {"type": "string"}
                            },
                            "required": ["username", "password"]
                        }
                    }
                }
            },
            "responses": {
                "200": {
                    "description": "Успешный вход",
                    "content": {
                        "application/json": {
                            "schema": {
                                "$ref": "#/components/schemas/Token"
                            }
                        }
                    }
                },
                "401": {
                    "description": "Неверные учетные данные"
                }
            }
        }
    }

    # Добавляем схемы данных
    openapi_schema["components"]["schemas"] = {
        "UserCreate": {
            "type": "object",
            "required": ["username", "email", "password"],
            "properties": {
                "username": {"type": "string", "minLength": 3, "maxLength": 50},
                "email": {"type": "string", "format": "email"},
                "password": {"type": "string", "minLength": 8},
                "full_name": {"type": "string"}
            }
        },
        "UserResponse": {
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "username": {"type": "string"},
                "email": {"type": "string"},
                "full_name": {"type": "string"},
                "balance": {"type": "number"},
                "rating": {"type": "number"},
                "is_active": {"type": "boolean"},
                "created_at": {"type": "string", "format": "date-time"}
            }
        },
        "Token": {
            "type": "object",
            "properties": {
                "access_token": {"type": "string"},
                "token_type": {"type": "string"}
            }
        }
    }

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi