import os
import logging
import math
from typing import Optional
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Integer, Text, ForeignKey, select, update as sql_update, delete as sql_delete
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)

# ============================================================================
# УТИЛИТЫ ДЛЯ КОНВЕРТАЦИИ
# ============================================================================

def minutes_to_seconds(minutes: int) -> int:
    """Конвертация минут в секунды"""
    return minutes * 60

def seconds_to_minutes_ceil(seconds: int) -> int:
    """Конвертация секунд в минуты с округлением вверх"""
    return math.ceil(seconds / 60)

# ============================================================================
# SQLALCHEMY МОДЕЛИ
# ============================================================================

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    
    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_name: Mapped[str] = mapped_column(String, nullable=False)
    remaining_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    permanent_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    iat: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    exp: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    tariff: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    payment_date: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    payment_status: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String, nullable=True, default="user")
    subscription_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    payment_system: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    subscription_status: Mapped[Optional[str]] = mapped_column(String, nullable=True)

class Topic(Base):
    __tablename__ = "topic"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

# ============================================================================
# DATABASE HANDLER
# ============================================================================

class DatabaseHandler:
    def __init__(self, database_url: str = None):
        """
        Инициализация обработчика БД
        
        Args:
            database_url: URL подключения к БД (например: postgresql+asyncpg://user:pass@localhost/dbname)
                         Если не указан - берется из переменной окружения DATABASE_URL
        """
        self.database_url = database_url or os.getenv(
            "DATABASE_URL",
            "postgresql+asyncpg://fluentgo_user:change_me_in_production@postgres:5432/fluentgo"
        )
        
        # Создаем async engine
        self.engine = create_async_engine(
            self.database_url,
            echo=False,  # Установить True для отладки SQL запросов
            pool_size=20,
            max_overflow=10,
            pool_pre_ping=True,  # Проверка соединения перед использованием
        )
        
        # Создаем session maker
        self.async_session = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        self._initialized = False
    
    async def initialize(self):
        """Инициализация базы данных при запуске"""
        if self._initialized:
            return
        
        try:
            # Создаем все таблицы
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            
            logger.info("Таблицы PostgreSQL созданы/проверены")
            
            # Создаем/обновляем тестовых пользователей
            await self._ensure_test_users()
            
            self._initialized = True
            logger.info("База данных PostgreSQL инициализирована успешно")
            
        except Exception as e:
            logger.error(f"Ошибка инициализации БД: {e}")
            raise
    
    async def _ensure_test_users(self):
        """Создает или обновляет тестовых пользователей"""
        test_users = [
            {
                "id": "zeqipe",
                "user_name": "zeqipe",
                "remaining_seconds": 7200,    # 120 минут сгораемых
                "permanent_seconds": 2700,    # 45 минут несгораемых
                "email": "test1@example.com",
                "tariff": "standart",
                "status": "vip",
                "payment_status": "active"
            },
            {
                "id": "dany",
                "user_name": "dany",
                "remaining_seconds": 18000,   # 300 минут сгораемых
                "permanent_seconds": 0,
                "email": "test2@example.com",
                "tariff": "pro",
                "payment_status": "active"
            },
            {
                "id": "demo_user",
                "user_name": "demo_user",
                "remaining_seconds": 0,
                "permanent_seconds": 5,       # 5 секунд для демо
                "email": "demo@fluentgo.com",
                "tariff": "free-guest",
                "status": "CMO",
                "payment_status": "active"
            }
        ]
        
        async with self.async_session() as session:
            for user_data in test_users:
                user_id = user_data["id"]
                
                # Проверяем существование пользователя
                result = await session.execute(
                    select(User).where(User.id == user_id)
                )
                existing_user = result.scalar_one_or_none()
                
                if existing_user:
                    # Обновляем существующего
                    for key, value in user_data.items():
                        setattr(existing_user, key, value)
                    logger.info(f"Пользователь {user_id} обновлен")
                else:
                    # Создаем нового
                    new_user = User(**user_data)
                    session.add(new_user)
                    logger.info(f"Пользователь {user_id} создан")
            
            await session.commit()
    
    async def get_user(self, user_id: str) -> Optional[dict]:
        """Получение данных пользователя по ID"""
        async with self.async_session() as session:
            result = await session.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                return None
            
            # Преобразуем ORM объект в словарь
            return {
                "id": user.id,
                "user_name": user.user_name,
                "remaining_seconds": user.remaining_seconds,
                "permanent_seconds": user.permanent_seconds,
                "iat": user.iat,
                "exp": user.exp,
                "email": user.email,
                "tariff": user.tariff,
                "payment_date": user.payment_date,
                "payment_status": user.payment_status,
                "status": user.status,
                "subscription_id": user.subscription_id,
                "payment_system": user.payment_system,
                "subscription_status": user.subscription_status
            }
    
    async def create_user(
        self,
        user_id: str,
        user_name: str,
        email: str = None,
        remaining_seconds: int = 0,
        permanent_seconds: int = 0,
        iat: int = None,
        exp: int = None,
        tariff: str = "free-guest",
        payment_status: str = "unpaid",
        payment_date: int = None,
        status: str = "user"
    ) -> bool:
        """Создание нового пользователя"""
        try:
            async with self.async_session() as session:
                new_user = User(
                    id=user_id,
                    user_name=user_name,
                    email=email,
                    remaining_seconds=remaining_seconds,
                    permanent_seconds=permanent_seconds,
                    iat=iat,
                    exp=exp,
                    tariff=tariff,
                    payment_status=payment_status,
                    payment_date=payment_date,
                    status=status
                )
                session.add(new_user)
                await session.commit()
                return True
        except IntegrityError:
            logger.warning(f"Пользователь с ID {user_id} уже существует")
            return False
        except Exception as e:
            logger.error(f"Ошибка создания пользователя {user_id}: {e}")
            return False
    
    async def update_user(self, user_id: str, **kwargs) -> bool:
        """Обновление данных пользователя"""
        if not kwargs:
            return False
        
        # Фильтруем только допустимые поля
        allowed_fields = {
            'user_name', 'remaining_seconds', 'permanent_seconds', 'iat', 'exp',
            'email', 'tariff', 'payment_date', 'payment_status', 'status',
            'subscription_id', 'payment_system', 'subscription_status'
        }
        
        update_data = {k: v for k, v in kwargs.items() if k in allowed_fields}
        
        if not update_data:
            return False
        
        try:
            async with self.async_session() as session:
                await session.execute(
                    sql_update(User).where(User.id == user_id).values(**update_data)
                )
                await session.commit()
                return True
        except Exception as e:
            logger.error(f"Ошибка обновления пользователя {user_id}: {e}")
            return False
    
    async def get_remaining_seconds(self, user_id: str) -> int:
        """Получение общего количества оставшихся секунд (обычные + несгораемые)"""
        user = await self.get_user(user_id)
        if not user:
            return 0
        
        return user.get('remaining_seconds', 0) + user.get('permanent_seconds', 0)
    
    async def get_remaining_minutes(self, user_id: str) -> int:
        """Получение оставшихся минут пользователя (с округлением вверх)"""
        seconds = await self.get_remaining_seconds(user_id)
        return seconds_to_minutes_ceil(seconds)
    
    async def decrease_seconds(self, user_id: str, seconds: int) -> bool:
        """
        Уменьшение оставшегося времени пользователя в секундах
        Сначала тратятся обычные секунды, затем несгораемые
        """
        user = await self.get_user(user_id)
        if not user:
            return False
        
        regular_seconds = user.get('remaining_seconds', 0)
        permanent_seconds = user.get('permanent_seconds', 0)
        
        if regular_seconds >= seconds:
            # Хватает обычных секунд
            new_regular = regular_seconds - seconds
            return await self.update_user(user_id, remaining_seconds=new_regular)
        else:
            # Обычных не хватает, тратим все обычные и часть несгораемых
            seconds_from_permanent = seconds - regular_seconds
            new_permanent = max(0, permanent_seconds - seconds_from_permanent)
            
            return await self.update_user(
                user_id,
                remaining_seconds=0,
                permanent_seconds=new_permanent
            )
    
    async def add_minutes(self, user_id: str, minutes: int) -> bool:
        """Добавление обычных минут пользователю (по тарифному плану)"""
        seconds_to_add = minutes_to_seconds(minutes)
        user = await self.get_user(user_id)
        if not user:
            return False
        
        new_seconds = user.get('remaining_seconds', 0) + seconds_to_add
        return await self.update_user(user_id, remaining_seconds=new_seconds)
    
    async def add_permanent_minutes(self, user_id: str, minutes: int) -> bool:
        """Добавление несгораемых минут пользователю"""
        seconds_to_add = minutes_to_seconds(minutes)
        user = await self.get_user(user_id)
        if not user:
            return False
        
        new_seconds = user.get('permanent_seconds', 0) + seconds_to_add
        return await self.update_user(user_id, permanent_seconds=new_seconds)
    
    async def get_regular_seconds(self, user_id: str) -> int:
        """Получение только обычных секунд (по тарифному плану)"""
        user = await self.get_user(user_id)
        return user.get('remaining_seconds', 0) if user else 0
    
    async def get_permanent_seconds(self, user_id: str) -> int:
        """Получение только несгораемых секунд"""
        user = await self.get_user(user_id)
        return user.get('permanent_seconds', 0) if user else 0
    
    async def set_regular_minutes(self, user_id: str, minutes: int) -> bool:
        """Установка обычных минут (например, при обновлении подписки)"""
        seconds = minutes_to_seconds(minutes)
        return await self.update_user(user_id, remaining_seconds=seconds)
    
    async def close(self):
        """Закрытие соединения с БД"""
        await self.engine.dispose()

# ============================================================================
# TOPIC HANDLER
# ============================================================================

class TopicHandler:
    def __init__(self, db_handler: DatabaseHandler = None):
        """
        Инициализация обработчика тем
        
        Args:
            db_handler: Экземпляр DatabaseHandler. Если не указан - создается новый
        """
        self.db_handler = db_handler
        self.logger = logging.getLogger(__name__)
        
        # Создаем папку logs если её нет
        log_file = 'logs/topic_operations.log'
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        
        # Настройка логирования в файл
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        self.logger.setLevel(logging.INFO)
    
    def _get_session(self):
        """Получение сессии БД"""
        if self.db_handler:
            return self.db_handler.async_session()
        else:
            # Fallback на глобальный db_handler
            return db_handler.async_session()
    
    async def create_topic(self, user_id: str, title: str, description: str) -> dict:
        """Создание новой темы"""
        try:
            async with self._get_session() as session:
                new_topic = Topic(
                    user_id=user_id,
                    title=title,
                    description=description
                )
                session.add(new_topic)
                await session.flush()  # Получаем ID до коммита
                topic_id = new_topic.id
                await session.commit()
                
                self.logger.info(f"Создана тема ID:{topic_id} для пользователя {user_id}")
                return {"status": "success", "topic_id": topic_id}
        except Exception as e:
            self.logger.error(f"Ошибка создания темы для пользователя {user_id}: {e}")
            return {"status": "error", "message": str(e)}
    
    async def get_user_topics(self, user_id: str) -> dict:
        """Получение всех тем пользователя"""
        try:
            async with self._get_session() as session:
                result = await session.execute(
                    select(Topic).where(Topic.user_id == user_id)
                )
                topics = result.scalars().all()
                
                topics_list = [
                    {
                        "id": topic.id,
                        "title": topic.title,
                        "description": topic.description
                    }
                    for topic in topics
                ]
                
                self.logger.info(f"Получено {len(topics_list)} тем для пользователя {user_id}")
                return {"status": "success", "topics": topics_list}
        except Exception as e:
            self.logger.error(f"Ошибка получения тем для пользователя {user_id}: {e}")
            return {"status": "error", "message": str(e)}
    
    async def update_topic(self, topic_id: int, user_id: str, title: str, description: str) -> dict:
        """Обновление темы"""
        try:
            async with self._get_session() as session:
                # Получаем тему
                result = await session.execute(
                    select(Topic).where(Topic.id == topic_id)
                )
                topic = result.scalar_one_or_none()
                
                if not topic:
                    self.logger.warning(f"Тема ID:{topic_id} не найдена")
                    return {"status": "error", "message": "Тема не найдена"}
                
                if topic.user_id != user_id:
                    self.logger.warning(f"Пользователь {user_id} пытался изменить чужую тему ID:{topic_id}")
                    return {"status": "forbidden", "message": "Доступ запрещен"}
                
                # Обновляем тему
                topic.title = title
                topic.description = description
                await session.commit()
                
                self.logger.info(f"Обновлена тема ID:{topic_id} пользователем {user_id}")
                return {"status": "success"}
        except Exception as e:
            self.logger.error(f"Ошибка обновления темы ID:{topic_id} пользователем {user_id}: {e}")
            return {"status": "error", "message": str(e)}
    
    async def delete_topic(self, topic_id: int, user_id: str) -> dict:
        """Удаление темы"""
        try:
            async with self._get_session() as session:
                # Получаем тему
                result = await session.execute(
                    select(Topic).where(Topic.id == topic_id)
                )
                topic = result.scalar_one_or_none()
                
                if not topic:
                    self.logger.warning(f"Тема ID:{topic_id} не найдена")
                    return {"status": "error", "message": "Тема не найдена"}
                
                if topic.user_id != user_id:
                    self.logger.warning(f"Пользователь {user_id} пытался удалить чужую тему ID:{topic_id}")
                    return {"status": "forbidden", "message": "Доступ запрещен"}
                
                # Удаляем тему
                await session.delete(topic)
                await session.commit()
                
                self.logger.info(f"Удалена тема ID:{topic_id} пользователем {user_id}")
                return {"status": "success"}
        except Exception as e:
            self.logger.error(f"Ошибка удаления темы ID:{topic_id} пользователем {user_id}: {e}")
            return {"status": "error", "message": str(e)}

# ============================================================================
# ГЛОБАЛЬНЫЕ ЭКЗЕМПЛЯРЫ
# ============================================================================

db_handler = DatabaseHandler()
topic_handler = TopicHandler(db_handler)

# ============================================================================
# ЭКСПОРТЫ
# ============================================================================

__all__ = [
    # Утилиты
    'minutes_to_seconds',
    'seconds_to_minutes_ceil',
    # Модели
    'Base',
    'User',
    'Topic',
    # Обработчики
    'DatabaseHandler',
    'TopicHandler',
    # Глобальные экземпляры
    'db_handler',
    'topic_handler',
]
