"""
Микросервис уведомлений
"""
from fastapi import FastAPI, BackgroundTasks
import logging
import sys
from pathlib import Path
from datetime import datetime
import threading
import time
from pydantic import BaseModel, EmailStr
from typing import Optional

# Добавляем корневую директорию в путь Python
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.rabbitmq import rabbitmq_client

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Notification Service",
    description="Микросервис для обработки и отправки уведомлений",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)


class NotificationHandler:
    """Обработчик уведомлений"""

    def __init__(self):
        self.notifications = []

    def handle_task_created(self, message: dict):
        """Обработка уведомления о создании задания"""
        logger.info(f" Уведомление: Создано задание #{message.get('task_id')}")
        logger.info(f"   Название: {message.get('title')}")
        logger.info(f"   Создатель: {message.get('creator_username')}")
        logger.info(f"   Цена: {message.get('price')}")

        # Здесь можно добавить отправку email, push-уведомлений и т.д.
        # Например: send_email(message['creator_id'], "Задание создано", ...)

        self.notifications.append({
            "type": "task_created",
            "task_id": message.get('task_id'),
            "timestamp": datetime.utcnow().isoformat(),
            "data": message
        })

    def handle_task_taken(self, message: dict):
        """Обработка уведомления о взятии задания"""
        logger.info(f" Уведомление: Задание #{message.get('task_id')} взято на выполнение")
        logger.info(f"   Исполнитель: {message.get('executor_username')}")

        self.notifications.append({
            "type": "task_taken",
            "task_id": message.get('task_id'),
            "timestamp": datetime.utcnow().isoformat(),
            "data": message
        })

    def handle_task_completed(self, message: dict):
        """Обработка уведомления о завершении задания"""
        logger.info(f" Уведомление: Задание #{message.get('task_id')} завершено")
        logger.info(f"   Выплата: {message.get('price')}")
        logger.info(f"   Исполнитель: {message.get('executor_username')}")

        self.notifications.append({
            "type": "task_completed",
            "task_id": message.get('task_id'),
            "timestamp": datetime.utcnow().isoformat(),
            "data": message
        })

    def process_notification(self, message: dict, routing_key: str):
        """Обработка входящего уведомления"""
        try:
            if "task.created" in routing_key:
                self.handle_task_created(message)
            elif "task.taken" in routing_key:
                self.handle_task_taken(message)
            elif "task.completed" in routing_key:
                self.handle_task_completed(message)
            else:
                logger.warning(f"Неизвестный тип уведомления: {routing_key}")

        except Exception as e:
            logger.error(f"Ошибка обработки уведомления: {e}")


# Создаем обработчик
notification_handler = NotificationHandler()


def rabbitmq_callback(message: dict):
    """Callback для RabbitMQ сообщений"""
    # В реальном RabbitMQ routing_key передается отдельно,
    # но для простоты будем определять тип по содержимому
    if "creator_username" in message and "price" in message:
        notification_handler.handle_task_created(message)
    elif "executor_username" in message and "creator_id" in message:
        notification_handler.handle_task_taken(message)
    elif "price" in message and "executor_username" in message:
        notification_handler.handle_task_completed(message)


def start_rabbitmq_consumer():
    """Запуск потребителя RabbitMQ"""
    try:
        logger.info("Запуск потребителя RabbitMQ...")

        # В реальном приложении здесь был бы вызов rabbitmq_client.consume_messages
        # Для демонстрации просто логируем
        logger.info("Потребитель RabbitMQ готов к работе")

        # Имитация работы потребителя
        while True:
            time.sleep(10)
            # В реальном приложении здесь было бы ожидание сообщений

    except Exception as e:
        logger.error(f"Ошибка потребителя RabbitMQ: {e}")


@app.on_event("startup")
async def startup_event():
    """Действия при запуске сервиса"""
    logger.info("Notification Service запущен")

    # Запускаем потребитель RabbitMQ в отдельном потоке
    if rabbitmq_client.is_enabled:
        consumer_thread = threading.Thread(
            target=start_rabbitmq_consumer,
            daemon=True
        )
        consumer_thread.start()
    else:
        logger.warning("RabbitMQ отключен, уведомления будут только в логах")


@app.get("/")
async def root():
    """
    Корневой endpoint
    """
    return {
        "service": "notification",
        "version": "1.0.0",
        "status": "running",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/health")
async def health_check():
    """
    Проверка здоровья сервиса
    """
    return {
        "status": "healthy",
        "service": "notification",
        "timestamp": datetime.utcnow().isoformat(),
        "rabbitmq_enabled": rabbitmq_client.is_enabled,
        "notifications_count": len(notification_handler.notifications)
    }


@app.get("/notifications")
async def get_notifications(limit: int = 50):
    """
    Получение списка уведомлений

    - **limit**: Максимальное количество уведомлений
    """
    notifications = notification_handler.notifications[-limit:]  # Последние N
    return {
        "count": len(notifications),
        "notifications": notifications
    }


@app.post("/notifications/test")
async def test_notification(
        notification_type: str,
        background_tasks: BackgroundTasks
):
    """
    Тестовое уведомление

    - **notification_type**: Тип уведомления (task_created, task_taken, task_completed)
    """
    test_messages = {
        "task_created": {
            "task_id": 999,
            "title": "Тестовое задание",
            "creator_username": "test_user",
            "price": 1000.0,
            "timestamp": datetime.utcnow().isoformat()
        },
        "task_taken": {
            "task_id": 999,
            "executor_username": "executor_user",
            "creator_id": 1,
            "title": "Тестовое задание",
            "timestamp": datetime.utcnow().isoformat()
        },
        "task_completed": {
            "task_id": 999,
            "executor_username": "executor_user",
            "creator_username": "test_user",
            "price": 1000.0,
            "timestamp": datetime.utcnow().isoformat()
        }
    }

    if notification_type not in test_messages:
        return {
            "error": "Неизвестный тип уведомления",
            "available_types": list(test_messages.keys())
        }

    message = test_messages[notification_type]

    # Обрабатываем уведомление
    if notification_type == "task_created":
        notification_handler.handle_task_created(message)
    elif notification_type == "task_taken":
        notification_handler.handle_task_taken(message)
    elif notification_type == "task_completed":
        notification_handler.handle_task_completed(message)

    return {
        "message": "Тестовое уведомление отправлено",
        "type": notification_type,
        "data": message
    }


if __name__ == "__main__":
    import uvicorn

    print(f"Запуск Notification Service на порту 8004...")
    print(f"Документация API: http://localhost:8004/docs")

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8004,
        reload=True,
        log_level="info"
    )
