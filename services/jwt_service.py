import jwt
import os
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from database import db_handler

# Загружаем переменные из .env файла
load_dotenv()

# Получаем секретный ключ из .env
JWT_SECRET_KEY = os.getenv("JWT_secret")
JWT_ALGORITHM = "HS256"

if not JWT_SECRET_KEY:
    raise ValueError("JWT_secret не найден в .env файле")

class JWTService:
    """Сервис для работы с JWT токенами"""
    
    @staticmethod
    def decode_token(token: str) -> Optional[Dict[str, Any]]:
        """Расшифровка JWT токена"""
        try:
            payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
    
    @staticmethod
    async def verify_user_from_token(token: str) -> Optional[Dict[str, Any]]:
        """Проверка токена и получение данных пользователя из БД"""
        # Расшифровываем токен
        payload = JWTService.decode_token(token)
        if not payload:
            return None
        
        # Получаем user_id из токена
        user_id = payload.get('user_id') or payload.get('sub')
        if not user_id:
            return None
        
        # Получаем пользователя из БД
        user = await db_handler.get_user(user_id)
        if not user:
            # Пользователя нет в БД - создаем нового с базовыми настройками
            user_name = payload.get('name') or payload.get('username') or f"user_{user_id}"
            email = payload.get('email')
            iat = payload.get('iat')
            exp = payload.get('exp')
            
            # Создаем пользователя с базовым тарифом
            success = await db_handler.create_user(
                user_id=user_id,
                user_name=user_name,
                remaining_seconds=120,  # 2 минуты
                iat=iat,
                exp=exp,
                email=email
            )
            
            if not success:
                return None
            
            # Обновляем базовую тарифную информацию
            await db_handler.update_user(
                user_id=user_id,
                tariff="free",  # Базовый бесплатный тариф
                payment_status="unpaid"  # Не оплачен
            )
            
            # Получаем созданного пользователя
            user = await db_handler.get_user(user_id)
            if not user:
                return None
        
        # Обновляем данные пользователя из токена (если есть)
        updates = {}
        if 'user_name' in payload:
            updates['user_name'] = payload['user_name']
        if 'email' in payload:
            updates['email'] = payload['email']
        if 'iat' in payload:
            updates['iat'] = payload['iat']
        if 'exp' in payload:
            updates['exp'] = payload['exp']
        
        if updates:
            await db_handler.update_user(user_id, **updates)
            # Получаем обновленные данные
            user = await db_handler.get_user(user_id)
        
        return user
