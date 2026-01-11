"""
Микросервис аутентификации и авторизации
"""
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
import logging
import sys
from pathlib import Path
from shared.database import get_db, Base, engine
from shared.models import User
from shared.schemas import UserCreate, UserResponse, Token
from shared.security import create_access_token
from datetime import datetime, timedelta
import os

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
    title="Auth Service",
    description="Микросервис для аутентификации и авторизации пользователей",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


@app.on_event("startup")
async def startup_event():
    """Действия при запуске сервиса"""
    logger.info("Auth Service запущен")


@app.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """
    Регистрация нового пользователя

    - **username**: Уникальное имя пользователя (3-50 символов)
    - **email**: Email пользователя
    - **password**: Пароль (минимум 8 символов)
    - **full_name**: Полное имя (опционально)
    """
    try:
        logger.info(f"Попытка регистрации пользователя: {user_data.username}")

        # Проверяем существование пользователя
        existing_user = db.query(User).filter(
            (User.username == user_data.username) | (User.email == user_data.email)
        ).first()

        if existing_user:
            logger.warning(f"Пользователь {user_data.username} или email уже существует")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Имя пользователя или email уже зарегистрированы"
            )

        # Создаем нового пользователя
        hashed_password = User.get_password_hash(user_data.password)
        new_user = User(
            username=user_data.username,
            email=user_data.email,
            hashed_password=hashed_password,
            full_name=user_data.full_name,
            balance=0.0,
            rating=5.0,
            is_active=True
        )

        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        logger.info(f"Пользователь {user_data.username} успешно зарегистрирован")
        return new_user

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при регистрации: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не удалось зарегистрировать пользователя"
        )


@app.post("/login", response_model=Token)
async def login(
        form_data: OAuth2PasswordRequestForm = Depends(),
        db: Session = Depends(get_db)
):
    """
    Аутентификация пользователя и получение JWT токена

    - **username**: Имя пользователя
    - **password**: Пароль
    """
    try:
        logger.info(f"Попытка входа пользователя: {form_data.username}")

        # Ищем пользователя
        user = db.query(User).filter(User.username == form_data.username).first()

        if not user:
            logger.warning(f"Пользователь {form_data.username} не найден")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверное имя пользователя или пароль",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Проверяем пароль
        if not user.verify_password(form_data.password):
            logger.warning(f"Неверный пароль для пользователя {form_data.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверное имя пользователя или пароль",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Проверяем активность
        if not user.is_active:
            logger.warning(f"Пользователь {form_data.username} неактивен")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Пользователь неактивен"
            )

        # Создаем токен
        access_token_expires = timedelta(
            minutes=int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))
        )
        access_token = create_access_token(
            data={"sub": user.username},
            expires_delta=access_token_expires
        )

        logger.info(f"Пользователь {form_data.username} успешно вошел в систему")
        return {"access_token": access_token, "token_type": "bearer"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при входе: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не удалось выполнить вход"
        )


@app.get("/me", response_model=UserResponse)
async def read_users_me(
        token: str = Depends(oauth2_scheme),
        db: Session = Depends(get_db)
):
    """
    Получение информации о текущем пользователе
    """
    try:
        from shared.security import verify_token

        # Верифицируем токен
        payload = verify_token(token)
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверный токен"
            )

        username = payload.get("sub")
        user = db.query(User).filter(User.username == username).first()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Пользователь не найден"
            )

        return user

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения информации о пользователе: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не удалось получить информацию о пользователе"
        )


@app.get("/health")
async def health_check():
    """
    Проверка здоровья сервиса
    """
    return {
        "status": "healthy", "service": "auth",
        "timestamp": datetime.utcnow().isoformat()
    }


if __name__ == "__main__":
    import uvicorn

    print(f"Запуск Auth Service на порту 8001...")
    print(f"Время запуска: {datetime.now()}")
    print(f"Документация API: http://localhost:8001/docs")

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info"
    )
