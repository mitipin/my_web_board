"""
Модуль для безопасности и JWT токенов
"""
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
import logging

# Импортируем конфигурацию
from config import JWT_CONFIG, SECURITY_CONFIG

# Настройка логирования
logger = logging.getLogger(__name__)

# Контекст для хеширования паролей
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=SECURITY_CONFIG["password_hash_rounds"]
)

# Конфигурация JWT
SECRET_KEY = JWT_CONFIG["secret_key"]
ALGORITHM = JWT_CONFIG["algorithm"]
ACCESS_TOKEN_EXPIRE_MINUTES = JWT_CONFIG["access_token_expire_minutes"]

logger.info(f"Инициализация модуля безопасности (JWT алгоритм: {ALGORITHM})")

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Создание JWT токена"""
    try:
        to_encode = data.copy()

        # Устанавливаем время истечения
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),  # Время создания
            "iss": "quest-board-api",  # Издатель
            "aud": "quest-board-users"  # Аудитория
        })

        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        logger.debug(f"Создан JWT токен для пользователя: {data.get('sub', 'unknown')}")
        return encoded_jwt

    except Exception as e:
        logger.error(f"Ошибка создания JWT токена: {e}")
        raise

def verify_token(token: str) -> Optional[dict]:
    """Верификация JWT токена"""
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            audience="quest-board-users",
            issuer="quest-board-api"
        )

        # Проверяем время истечения
        expire = payload.get("exp")
        if expire is None:
            logger.warning("JWT токен без времени истечения")
            return None

        if datetime.utcnow() > datetime.fromtimestamp(expire):
            logger.warning("JWT токен истек")
            return None

        logger.debug(f"JWT токен верифицирован для пользователя: {payload.get('sub', 'unknown')}")
        return payload

    except JWTError as e:
        logger.warning(f"Ошибка верификации JWT токена: {e}")
        return None
    except Exception as e:
        logger.error(f"Неожиданная ошибка при верификации токена: {e}")
        return None

def get_password_hash(password: str) -> str:
    """Хеширование пароля"""
    try:
        if len(password) < SECURITY_CONFIG["password_min_length"]:
            raise ValueError(f"Пароль должен содержать минимум {SECURITY_CONFIG['password_min_length']} символов")

        hashed = pwd_context.hash(password)
        logger.debug("Пароль успешно хеширован")
        return hashed
    except Exception as e:
        logger.error(f"Ошибка хеширования пароля: {e}")
        raise

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверка пароля"""
    try:
        is_valid = pwd_context.verify(plain_password, hashed_password)
        if not is_valid:
            logger.warning("Неверный пароль")
        return is_valid
    except Exception as e:
        logger.error(f"Ошибка проверки пароля: {e}")
        return False

def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    Проверка сложности пароля

    Возвращает (is_valid, message)
    """
    if len(password) < SECURITY_CONFIG["password_min_length"]:
        return False, f"Пароль должен содержать минимум {SECURITY_CONFIG['password_min_length']} символов"

    # Проверка на наличие цифр
    if not any(char.isdigit() for char in password):
        return False, "Пароль должен содержать хотя бы одну цифру"

     # Проверка на наличие букв в верхнем регистре
    if not any(char.isupper() for char in password):
        return False, "Пароль должен содержать хотя бы одну заглавную букву"

    # Проверка на наличие букв в нижнем регистре
    if not any(char.islower() for char in password):
        return False, "Пароль должен содержать хотя бы одну строчную букву"

    return True, "Пароль соответствует требованиям безопасности"

