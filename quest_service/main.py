"""
Микросервис управления заданиями (квестами)
"""
from fastapi import FastAPI, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import logging
import sys
from pathlib import Path
from datetime import datetime

# Добавляем корневую директорию в путь Python
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.database import get_db, Base, engine
from shared.models import Task, User
from shared.schemas import TaskCreate, TaskResponse, TaskStatus
from shared.rabbitmq import rabbitmq_client
from shared.security import verify_token

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
    title="Quest Service",
    description="Микросервис для управления заданиями (квестами)",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)


def get_current_user(authorization: str = Query(..., alias="Authorization"),
                     db: Session = Depends(get_db)):
    """
    Получение текущего пользователя из заголовка Authorization
    """
    try:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Требуется аутентификация"
            )

        token = authorization.split("Bearer ")[1]
        payload = verify_token(token)

        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверный токен"
            )

        username = payload.get("sub")
        if not username:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверный токен"
            )

        user = db.query(User).filter(User.username == username).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Пользователь не найден"
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Пользователь неактивен"
            )

        return user

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка аутентификации: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ошибка аутентификации"
        )


@app.on_event("startup")
async def startup_event():
    """Действия при запуске сервиса"""
    logger.info("Quest Service запущен")


@app.post("/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
        task_data: TaskCreate,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Создание нового задания (квеста)

    - **title**: Название задания (5-200 символов)
    - **description**: Описание задания
    - **price**: Цена задания (должна быть > 0)
    - **category**: Категория задания
    - **deadline**: Срок выполнения
    """
    try:
        logger.info(f"Создание задания пользователем {current_user.username}")

        # Проверяем баланс пользователя
        if current_user.balance < task_data.price:
            logger.warning(f"Недостаточно средств у пользователя {current_user.username}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Недостаточно средств на балансе"
            )

        # Создаем задание
        task = Task(
            title=task_data.title,
            description=task_data.description,
            price=task_data.price,
            category=task_data.category,
            deadline=task_data.deadline,
            creator_id=current_user.id,
            status=TaskStatus.OPEN
        )

        db.add(task)
        db.commit()
        db.refresh(task)

        # Отправляем уведомление через RabbitMQ
        rabbitmq_client.publish_message(
            exchange="notifications",
            routing_key="task.created",
            message={
                "task_id": task.id,
                "title": task.title,
                "creator_id": current_user.id,
                "creator_username": current_user.username,
                "price": task.price,
                "timestamp": datetime.utcnow().isoformat()
            }
        )

        logger.info(f"Задание {task.id} успешно создано")
        return task

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка создания задания: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не удалось создать задание"
        )


@app.get("/tasks", response_model=List[TaskResponse])
async def get_tasks(
        status: Optional[TaskStatus] = None,
        category: Optional[str] = None,
        min_price: Optional[float] = Query(None, ge=0),
        max_price: Optional[float] = Query(None, ge=0),
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=1000),
        db: Session = Depends(get_db)
):
    """
    Получение списка заданий с фильтрацией

    - **status**: Фильтр по статусу
    - **category**: Фильтр по категории
    - **min_price**: Минимальная цена
    - **max_price**: Максимальная цена
    - **skip**: Пропустить первые N записей
    - **limit**: Ограничить количество записей (макс. 1000)
    """
    try:
        logger.info(f"Получение списка заданий с фильтрами")

        query = db.query(Task)

        if status:
            query = query.filter(Task.status == status)
        if category:
            query = query.filter(Task.category == category)
        if min_price is not None:
            query = query.filter(Task.price >= min_price)
        if max_price is not None:
            query = query.filter(Task.price <= max_price)

        # Сортируем по дате создания (новые сначала)
        query = query.order_by(Task.created_at.desc())

        tasks = query.offset(skip).limit(limit).all()

        logger.info(f"Найдено {len(tasks)} заданий")
        return tasks

    except Exception as e:
        logger.error(f"Ошибка получения заданий: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не удалось получить список заданий"
        )


@app.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: int, db: Session = Depends(get_db)):
    """
    Получение информации о конкретном задании

    - **task_id**: ID задания
    """
    try:
        logger.info(f"Получение задания {task_id}")

        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            logger.warning(f"Задание {task_id} не найдено")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Задание не найдено"
            )

        return task

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения задания: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не удалось получить информацию о задании"
        )


@app.post("/tasks/{task_id}/take")
async def take_task(
        task_id: int,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Взятие задания на выполнение

    - **task_id**: ID задания
    """
    try:
        logger.info(f"Попытка взятия задания {task_id} пользователем {current_user.username}")

        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            logger.warning(f"Задание {task_id} не найдено")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Задание не найдено"
            )

        if task.status != TaskStatus.OPEN:
            logger.warning(f"Задание {task_id} недоступно для взятия (статус: {task.status})")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Задание недоступно для взятия"
            )

        if task.creator_id == current_user.id:
            logger.warning(f"Пользователь {current_user.username} пытается взять свое задание")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Нельзя взять свое задание"
            )

        # Обновляем задание
        task.status = TaskStatus.IN_PROGRESS
        task.executor_id = current_user.id
        task.updated_at = datetime.utcnow()

        db.commit()

        # Отправляем уведомление
        rabbitmq_client.publish_message(
            exchange="notifications",
            routing_key="task.taken",
            message={
                "task_id": task.id,
                "executor_id": current_user.id,
                "executor_username": current_user.username,
                "creator_id": task.creator_id,
                "title": task.title,
                "timestamp": datetime.utcnow().isoformat()
            }
        )

        logger.info(f"Задание {task_id} взято пользователем {current_user.username}")
        return {"message": "Задание успешно взято", "task_id": task_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка взятия задания: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не удалось взять задание"
        )


@app.post("/tasks/{task_id}/complete")
async def complete_task(
        task_id: int,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Завершение задания

    - **task_id**: ID задания
    """
    try:
        logger.info(f"Попытка завершения задания {task_id} пользователем {current_user.username}")

        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            logger.warning(f"Задание {task_id} не найдено")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Задание не найдено"
            )

        # Проверяем права
        if task.creator_id != current_user.id:
            logger.warning(f"Пользователь {current_user.username} не может завершить чужое задание")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Только создатель задания может завершить его"
            )

        if task.status != TaskStatus.IN_PROGRESS:
            logger.warning(f"Задание {task_id} не в процессе выполнения (статус: {task.status})")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Задание не в процессе выполнения"
            )

        if not task.executor_id:
            logger.warning(f"У задания {task_id} нет исполнителя")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="У задания нет исполнителя"
            )

        # Находим исполнителя
        executor = db.query(User).filter(User.id == task.executor_id).first()
        if not executor:
            logger.warning(f"Исполнитель {task.executor_id} не найден")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Исполнитель не найден"
            )

        # Проверяем баланс создателя
        if current_user.balance < task.price:
            logger.warning(f"Недостаточно средств у создателя задания {current_user.username}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Недостаточно средств для выплаты"
            )

        # Выполняем транзакцию
        task.status = TaskStatus.COMPLETED
        task.updated_at = datetime.utcnow()

        # Переводим средства
        current_user.balance -= task.price
        executor.balance += task.price

        # Обновляем рейтинг исполнителя (простая логика)
        executor.rating = min(5.0, executor.rating + 0.1)

        db.commit()

        # Отправляем уведомление
        rabbitmq_client.publish_message(
            exchange="notifications",
            routing_key="task.completed",
            message={
                "task_id": task.id,
                "executor_id": task.executor_id,
                "executor_username": executor.username,
                "creator_id": current_user.id,
                "creator_username": current_user.username,
                "price": task.price,
                "timestamp": datetime.utcnow().isoformat()
            }
        )

        logger.info(f"Задание {task_id} успешно завершено")
        return {
            "message": "Задание успешно завершено",
            "task_id": task_id,
            "payment": task.price
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка завершения задания: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не удалось завершить задание"
        )


@app.get("/users/{user_id}/tasks", response_model=List[TaskResponse])
async def get_user_tasks(
        user_id: int,
        role: str = Query("creator", regex="^(creator|executor)$"),
        db: Session = Depends(get_db)
):
    """
    Получение заданий пользователя

    - **user_id**: ID пользователя
    - **role**: Роль пользователя (creator - созданные, executor - взятые)
    """
    try:
        logger.info(f"Получение заданий пользователя {user_id} (роль: {role})")

        query = db.query(Task)

        if role == "creator":
            query = query.filter(Task.creator_id == user_id)
        else:
            query = query.filter(Task.executor_id == user_id)

        tasks = query.order_by(Task.created_at.desc()).all()

        logger.info(f"Найдено {len(tasks)} заданий для пользователя {user_id}")
        return tasks

    except Exception as e:
        logger.error(f"Ошибка получения заданий пользователя: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не удалось получить задания пользователя"
        )


@app.get("/health")
async def health_check():
    """
    Проверка здоровья сервиса
    """
    from datetime import datetime
    return {
        "status": "healthy",
        "service": "quest",
        "timestamp": datetime.utcnow().isoformat()
    }


if __name__ == "__main__":
    import uvicorn

    print(f"Запуск Quest Service на порту 8002...")
    print(f"Документация API: http://localhost:8002/docs")

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8002,
        reload=True,
        log_level="info"
    )
