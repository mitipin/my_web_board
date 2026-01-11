"""
Микросервис чата для общения по заданиям
"""
from fastapi import FastAPI, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
import logging
import sys
import json
from pathlib import Path
from typing import Dict, List
from shared.database import get_db, Base, engine
from shared.models import ChatMessage, Task, User
from shared.schemas import ChatMessageCreate, ChatMessageResponse
from shared.security import verify_token


# Добавляем корневую директорию в путь Python
sys.path.insert(0, str(Path(__file__).parent.parent))

# Создаем таблицы если их нет
try:
    Base.metadata.create_all(bind=engine)
    logging.info("Таблицы базы данных созданы/проверены")
except Exception as e:
    logging.warning(f"Ошибка создания таблиц: {e}")

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Chat Service",
    description="Микросервис для общения между пользователями по заданиям",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)


class ConnectionManager:
    """Менеджер WebSocket соединений"""

    def __init__(self):
        self.active_connections: Dict[int, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, task_id: int):
        """Подключение к WebSocket"""
        await websocket.accept()
        if task_id not in self.active_connections:
            self.active_connections[task_id] = []
        self.active_connections[task_id].append(websocket)
        logger.info(f"WebSocket подключен к заданию {task_id}")

    def disconnect(self, websocket: WebSocket, task_id: int):
        """Отключение от WebSocket"""
        if task_id in self.active_connections:
            if websocket in self.active_connections[task_id]:
                self.active_connections[task_id].remove(websocket)
                logger.info(f"WebSocket отключен от задания {task_id}")
            if not self.active_connections[task_id]:
                del self.active_connections[task_id]

    async def send_personal_message(self, message: str, websocket: WebSocket):
        """Отправка личного сообщения"""
        await websocket.send_text(message)

    async def broadcast(self, message: str, task_id: int, exclude: WebSocket = None):
        """Трансляция сообщения всем подключенным к заданию"""
        if task_id in self.active_connections:
            for connection in self.active_connections[task_id]:
                if connection != exclude:
                    try:
                        await connection.send_text(message)
                    except Exception as e:
                        logger.error(f"Ошибка отправки сообщения: {e}")


manager = ConnectionManager()


def get_current_user_from_token(token: str, db: Session) -> User:
    """Получение пользователя из токена"""
    try:
        payload = verify_token(token)
        if not payload:
            return None

        username = payload.get("sub")
        if not username:
            return None

        user = db.query(User).filter(User.username == username).first()
        return user
    except Exception as e:
        logger.error(f"Ошибка получения пользователя из токена: {e}")
        return None


def check_task_access(user: User, task: Task) -> bool:
    """Проверка доступа пользователя к заданию"""
    if not user or not task:
        return False

    # Доступ есть у создателя и исполнителя
    return user.id in [task.creator_id, task.executor_id]


@app.on_event("startup")
async def startup_event():
    """Действия при запуске сервиса"""
    logger.info("Chat Service запущен")


@app.post("/messages", response_model=ChatMessageResponse, status_code=status.HTTP_201_CREATED)
async def create_message(
        message_data: ChatMessageCreate,
        authorization: str = Depends(lambda: None),
        db: Session = Depends(get_db)
):
    """
    Отправка сообщения в чат задания

    - **task_id**: ID задания
    - **message**: Текст сообщения (1-2000 символов)
    """
    try:
        # Проверяем авторизацию
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Требуется аутентификация"
            )

        token = authorization.split("Bearer ")[1]
        current_user = get_current_user_from_token(token, db)

        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверный токен"
            )

        # Проверяем задание
        task = db.query(Task).filter(Task.id == message_data.task_id).first()
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Задание не найдено"
            )

        # Проверяем доступ
        if not check_task_access(current_user, task):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Нет доступа к чату этого задания"
            )

        # Создаем сообщение
        chat_message = ChatMessage(
            task_id=message_data.task_id,
            sender_id=current_user.id,
            message=message_data.message
        )

        db.add(chat_message)
        db.commit()
        db.refresh(chat_message)

        logger.info(f"Сообщение отправлено в задание {message_data.task_id} от пользователя {current_user.username}")

        # Транслируем через WebSocket
        await manager.broadcast(
            json.dumps({
                "type": "message",
                "id": chat_message.id,
                "task_id": chat_message.task_id,
                "sender_id": chat_message.sender_id,
                "sender_username": current_user.username,
                "message": chat_message.message,
                "created_at": chat_message.created_at.isoformat()
            }),
            message_data.task_id
        )

        return chat_message

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка отправки сообщения: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не удалось отправить сообщение"
        )


@app.get("/tasks/{task_id}/messages", response_model=List[ChatMessageResponse])
async def get_task_messages(
        task_id: int,
        authorization: str = Depends(lambda: None),
        skip: int = 0,
        limit: int = 100,
        db: Session = Depends(get_db)
):
    """
    Получение истории сообщений по заданию

    - **task_id**: ID задания
    - **skip**: Пропустить первые N сообщений
    - **limit**: Ограничить количество сообщений
    """
    try:
        # Проверяем авторизацию
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Требуется аутентификация"
            )

        token = authorization.split("Bearer ")[1]
        current_user = get_current_user_from_token(token, db)

        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверный токен"
            )

        # Проверяем задание
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Задание не найдено"
            )

        # Проверяем доступ
        if not check_task_access(current_user, task):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Нет доступа к чату этого задания"
            )

        # Получаем сообщения
        messages = db.query(ChatMessage) \
            .filter(ChatMessage.task_id == task_id) \
            .order_by(ChatMessage.created_at.desc()) \
            .offset(skip) \
            .limit(limit) \
            .all()

        # Возвращаем в правильном порядке (старые сначала)
        messages.reverse()

        logger.info(f"Получено {len(messages)} сообщений для задания {task_id}")
        return messages

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения сообщений: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не удалось получить сообщения"
        )


@app.websocket("/ws/{task_id}")
async def websocket_endpoint(
        websocket: WebSocket,
        task_id: int
):
    """
    WebSocket для реального времени чата

    - **task_id**: ID задания
    """
    db = next(get_db())

    try:
        # Получаем токен из query параметров
        token = websocket.query_params.get("token")
        if not token:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        # Аутентифицируем пользователя
        current_user = get_current_user_from_token(token, db)
        if not current_user:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        # Проверяем задание
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        # Проверяем доступ
        if not check_task_access(current_user, task):
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        # Подключаемся
        await manager.connect(websocket, task_id)

        # Отправляем информацию о подключении
        await websocket.send_text(json.dumps({
            "type": "connection",
            "message": "Подключено к чату задания",
            "task_id": task_id,
            "user_id": current_user.id,
            "username": current_user.username
        }))

        logger.info(f"Пользователь {current_user.username} подключился к WebSocket чата задания {task_id}")

        try:
            while True:
                # Получаем сообщение
                data = await websocket.receive_text()

                try:
                    message_data = json.loads(data)
                    message_text = message_data.get("message", "").strip()

                    if not message_text:
                        continue

                    # Сохраняем в базу
                    chat_message = ChatMessage(
                        task_id=task_id,
                        sender_id=current_user.id,
                        message=message_text
                    )

                    db.add(chat_message)
                    db.commit()
                    db.refresh(chat_message)

                    # Транслируем всем
                    await manager.broadcast(
                        json.dumps({
                            "type": "message",
                            "id": chat_message.id,
                            "task_id": task_id,
                            "sender_id": current_user.id,
                            "sender_username": current_user.username,
                            "message": message_text,
                            "created_at": chat_message.created_at.isoformat()
                        }),
                        task_id,
                        exclude=websocket
                    )

                    logger.info(f"WebSocket сообщение от {current_user.username} в задании {task_id}")

                except json.JSONDecodeError:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "Неверный формат сообщения"
                    }))
                except Exception as e:
                    logger.error(f"Ошибка обработки WebSocket сообщения: {e}")

        except WebSocketDisconnect:
            manager.disconnect(websocket, task_id)
            logger.info(f"WebSocket отключен для задания {task_id}")

    except Exception as e:
        logger.error(f"Ошибка WebSocket: {e}")
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR)


@app.get("/health")
async def health_check():
    """
    Проверка здоровья сервиса
    """
    from datetime import datetime
    return {
        "status": "healthy",
        "service": "chat",
        "timestamp": datetime.utcnow().isoformat(),
        "active_connections": sum(len(conns) for conns in manager.active_connections.values())
    }


if __name__ == "__main__":
    import uvicorn

    print(f"Запуск Chat Service на порту 8003...")
    print(f"Документация API: http://localhost:8003/docs")
    print(f"WebSocket endpoint: ws://localhost:8003/ws/{{task_id}}?token={{token}}")

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8003,
        reload=True,
        log_level="info"
    )
