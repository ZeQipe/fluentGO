import sqlite3
import asyncio
import aiosqlite
from pathlib import Path
import logging
import math

logger = logging.getLogger(__name__)

def minutes_to_seconds(minutes: int) -> int:
    """Конвертация минут в секунды"""
    return minutes * 60

def seconds_to_minutes_ceil(seconds: int) -> int:
    """Конвертация секунд в минуты с округлением вверх"""
    return math.ceil(seconds / 60)

class DatabaseHandler:
    def __init__(self, db_path: str = "users.db"):
        self.db_path = db_path
        self._initialized = False
    
    async def initialize(self):
        """Инициализация базы данных при запуске"""
        if self._initialized:
            return
            
        # Создаем директорию если не существует
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Проверяем существование БД
        db_exists = Path(self.db_path).exists()
        
        if not db_exists:
            logger.info("База данных не найдена. Создаем новую...")
            await self._create_database()
        else:
            logger.info("База данных найдена. Проверяем структуру...")
            await self._verify_database_structure()
        
        # Создаем/обновляем тестовых пользователей
        await self._ensure_test_users()
        
        self._initialized = True
        logger.info("База данных инициализирована успешно")
    
    async def _create_database(self):
        """Создание новой базы данных"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE users (
                    id TEXT PRIMARY KEY,
                    user_name TEXT NOT NULL,
                    remaining_seconds INTEGER NOT NULL DEFAULT 0,
                    permanent_seconds INTEGER NOT NULL DEFAULT 0,
                    iat INTEGER,
                    exp INTEGER,
                    email TEXT,
                    tariff TEXT,
                    payment_date INTEGER,
                    payment_status TEXT,
                    status TEXT
                )
            """)
            
            await db.execute("""
                CREATE TABLE topic (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            """)
            await db.commit()
            logger.info("Таблицы users и topic созданы")
    
    async def _verify_database_structure(self):
        """Проверка и обновление структуры существующей БД"""
        async with aiosqlite.connect(self.db_path) as db:
            # Получаем информацию о существующих колонках
            cursor = await db.execute("PRAGMA table_info(users)")
            columns = await cursor.fetchall()
            existing_columns = {col[1] for col in columns}
            
            required_columns = {
                'id': 'TEXT PRIMARY KEY',
                'user_name': 'TEXT NOT NULL',
                'remaining_seconds': 'INTEGER NOT NULL DEFAULT 0',
                'permanent_seconds': 'INTEGER NOT NULL DEFAULT 0',
                'iat': 'INTEGER',
                'exp': 'INTEGER',
                'email': 'TEXT',
                'tariff': 'TEXT',
                'payment_date': 'INTEGER',
                'payment_status': 'TEXT',
                'status': 'TEXT'
            }
            
            # Проверяем, есть ли старое поле remaining_time и нужно ли его мигрировать
            if 'remaining_time' in existing_columns and 'remaining_seconds' not in existing_columns:
                logger.info("Мигрируем remaining_time в remaining_seconds")
                # Добавляем новое поле
                await db.execute("ALTER TABLE users ADD COLUMN remaining_seconds INTEGER NOT NULL DEFAULT 0")
                # Копируем данные, конвертируя минуты в секунды
                await db.execute("UPDATE users SET remaining_seconds = remaining_time * 60")
                await db.commit()
                logger.info("Миграция завершена")
            
            # Проверяем наличие таблицы users
            cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
            table_exists = await cursor.fetchone()
            
            if not table_exists:
                logger.info("Таблица users не найдена. Создаем...")
                await self._create_database()
                return
            
            # Проверяем наличие таблицы topic
            cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='topic'")
            topic_table_exists = await cursor.fetchone()
            
            if not topic_table_exists:
                logger.info("Таблица topic не найдена. Создаем...")
                await db.execute("""
                    CREATE TABLE topic (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT NOT NULL,
                        title TEXT NOT NULL,
                        description TEXT NOT NULL,
                        FOREIGN KEY (user_id) REFERENCES users (id)
                    )
                """)
                await db.commit()
                logger.info("Таблица topic создана")
            
            # Добавляем недостающие колонки
            for column_name, column_type in required_columns.items():
                if column_name not in existing_columns:
                    logger.info(f"Добавляем недостающую колонку: {column_name}")
                    try:
                        await db.execute(f"ALTER TABLE users ADD COLUMN {column_name} {column_type}")
                    except sqlite3.OperationalError as e:
                        logger.warning(f"Не удалось добавить колонку {column_name}: {e}")
            
            await db.commit()
    
    async def _ensure_test_users(self):
        """Создает или обновляет тестовых пользователей"""
        test_users = [
            {
                "id": "zeqipe",
                "user_name": "zeqipe", 
                "remaining_seconds": 7200,    # 120 минут сгораемых (120 * 60)
                "permanent_seconds": 2700,    # 45 минут несгораемых (45 * 60)
                "email": "test1@example.com",
                "tariff": "standart"
            },
            {
                "id": "dany",
                "user_name": "dany",
                "remaining_seconds": 18000,   # 300 минут сгораемых (300 * 60)
                "permanent_seconds": 0,       # Нет несгораемых
                "email": "test2@example.com",
                "tariff": "pro"
            },
            {
                "id": "demo_user",
                "user_name": "demo_user",
                "remaining_seconds": 0,        # 5 секунд сгораемых
                "permanent_seconds": 5,       # Нет несгораемых
                "email": "demo@fluentgo.com", 
                "tariff": "free"
            }
        ]
        
        try:
            async with aiosqlite.connect(self.db_path) as db:
                for user_data in test_users:
                    user_id = user_data["id"]
                    user_seconds = user_data["remaining_seconds"]
                    permanent_seconds = user_data["permanent_seconds"]
                    
                    # Проверяем существование пользователя
                    cursor = await db.execute("SELECT id FROM users WHERE id = ?", (user_id,))
                    exists = await cursor.fetchone()
                    
                    if exists:
                        # Обновляем существующего пользователя
                        await db.execute(
                            "UPDATE users SET user_name = ?, remaining_seconds = ?, permanent_seconds = ?, email = ?, tariff = ?, payment_status = ?, status = ? WHERE id = ?",
                            (user_data["user_name"], user_seconds, permanent_seconds, user_data["email"], user_data["tariff"], "active", "user", user_id)
                        )
                        logger.info(f"Пользователь {user_id} обновлен: {user_seconds//60} обычных + {permanent_seconds//60} несгораемых минут, тариф {user_data['tariff']}")
                    else:
                        # Создаем нового пользователя
                        await db.execute("""
                            INSERT INTO users (id, user_name, remaining_seconds, permanent_seconds, iat, exp, email, tariff, payment_date, payment_status, status)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (user_id, user_data["user_name"], user_seconds, permanent_seconds, None, None, user_data["email"], user_data["tariff"], None, "active", "user"))
                        logger.info(f"Пользователь {user_id} создан: {user_seconds//60} обычных + {permanent_seconds//60} несгораемых минут, тариф {user_data['tariff']}")
                
                await db.commit()
        except Exception as e:
            logger.error(f"Ошибка создания/обновления тестовых пользователей: {e}")
    
    async def get_user(self, user_id: str) -> dict:
        """Получение данных пользователя по ID"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM users WHERE id = ?", (user_id,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    async def create_user(self, user_id: str, user_name: str, email: str,
                         remaining_seconds: int = 0, permanent_seconds: int = 0, 
                         iat: int = None, exp: int = None, tariff: str = "free",
                         payment_status: str = "unpaid", payment_date: int = None,
                         status: str = "user") -> bool:
        """Создание нового пользователя"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT INTO users (id, user_name, email, remaining_seconds, permanent_seconds, 
                                      iat, exp, tariff, payment_status, payment_date, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (user_id, user_name, email, remaining_seconds, permanent_seconds, 
                      iat, exp, tariff, payment_status, payment_date, status))
                await db.commit()
                return True
        except sqlite3.IntegrityError:
            logger.warning(f"Пользователь с ID {user_id} уже существует")
            return False
    
    async def update_user(self, user_id: str, **kwargs) -> bool:
        """Обновление данных пользователя"""
        if not kwargs:
            return False
        
        # Формируем SET часть запроса
        set_parts = []
        values = []
        for key, value in kwargs.items():
            if key in ['user_name', 'remaining_seconds', 'permanent_seconds', 'iat', 'exp', 'email', 'tariff', 'payment_date', 'payment_status', 'status']:
                set_parts.append(f"{key} = ?")
                values.append(value)
        
        if not set_parts:
            return False
        
        values.append(user_id)
        
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    f"UPDATE users SET {', '.join(set_parts)} WHERE id = ?",
                    values
                )
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Ошибка обновления пользователя {user_id}: {e}")
            return False
    
    async def get_remaining_seconds(self, user_id: str) -> int:
        """Получение общего количества оставшихся секунд (обычные + несгораемые)"""
        user = await self.get_user(user_id)
        if not user:
            return 0
        
        # Возвращаем сумму обычных и несгораемых секунд
        regular_seconds = user.get('remaining_seconds', 0)
        permanent_seconds = user.get('permanent_seconds', 0)
        return regular_seconds + permanent_seconds
    
    async def get_remaining_minutes(self, user_id: str) -> int:
        """Получение оставшихся минут пользователя (с округлением вверх)"""
        seconds = await self.get_remaining_seconds(user_id)
        return seconds_to_minutes_ceil(seconds)
    
    async def decrease_seconds(self, user_id: str, seconds: int) -> bool:
        """Уменьшение оставшегося времени пользователя в секундах
        Сначала тратятся обычные секунды, затем несгораемые"""
        user = await self.get_user(user_id)
        if not user:
            return False
        
        regular_seconds = user.get('remaining_seconds', 0)
        permanent_seconds = user.get('permanent_seconds', 0)
        
        # Сначала тратим обычные секунды
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

class TopicHandler:
    def __init__(self, db_path: str = "users.db"):
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)
        
        # Настройка логирования в файл
        file_handler = logging.FileHandler('topic_operations.log')
        file_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        self.logger.setLevel(logging.INFO)
    
    async def create_topic(self, user_id: str, title: str, description: str) -> dict:
        """Создание новой темы"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    INSERT INTO topic (user_id, title, description)
                    VALUES (?, ?, ?)
                """, (user_id, title, description))
                await db.commit()
                topic_id = cursor.lastrowid
                
                self.logger.info(f"Создана тема ID:{topic_id} для пользователя {user_id}")
                return {"status": "success", "topic_id": topic_id}
        except Exception as e:
            self.logger.error(f"Ошибка создания темы для пользователя {user_id}: {e}")
            return {"status": "error", "message": str(e)}
    
    async def get_user_topics(self, user_id: str) -> dict:
        """Получение всех тем пользователя"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute("""
                    SELECT id, title, description FROM topic WHERE user_id = ?
                """, (user_id,))
                rows = await cursor.fetchall()
                topics = [dict(row) for row in rows]
                
                self.logger.info(f"Получено {len(topics)} тем для пользователя {user_id}")
                return {"status": "success", "topics": topics}
        except Exception as e:
            self.logger.error(f"Ошибка получения тем для пользователя {user_id}: {e}")
            return {"status": "error", "message": str(e)}
    
    async def update_topic(self, topic_id: int, user_id: str, title: str, description: str) -> dict:
        """Обновление темы"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Проверяем принадлежность темы пользователю
                cursor = await db.execute("SELECT user_id FROM topic WHERE id = ?", (topic_id,))
                row = await cursor.fetchone()
                
                if not row:
                    self.logger.warning(f"Тема ID:{topic_id} не найдена")
                    return {"status": "error", "message": "Тема не найдена"}
                
                if row[0] != user_id:
                    self.logger.warning(f"Пользователь {user_id} пытался изменить чужую тему ID:{topic_id}")
                    return {"status": "forbidden", "message": "Доступ запрещен"}
                
                # Обновляем тему
                await db.execute("""
                    UPDATE topic SET title = ?, description = ? WHERE id = ?
                """, (title, description, topic_id))
                await db.commit()
                
                self.logger.info(f"Обновлена тема ID:{topic_id} пользователем {user_id}")
                return {"status": "success"}
        except Exception as e:
            self.logger.error(f"Ошибка обновления темы ID:{topic_id} пользователем {user_id}: {e}")
            return {"status": "error", "message": str(e)}
    
    async def delete_topic(self, topic_id: int, user_id: str) -> dict:
        """Удаление темы"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Проверяем принадлежность темы пользователю
                cursor = await db.execute("SELECT user_id FROM topic WHERE id = ?", (topic_id,))
                row = await cursor.fetchone()
                
                if not row:
                    self.logger.warning(f"Тема ID:{topic_id} не найдена")
                    return {"status": "error", "message": "Тема не найдена"}
                
                if row[0] != user_id:
                    self.logger.warning(f"Пользователь {user_id} пытался удалить чужую тему ID:{topic_id}")
                    return {"status": "forbidden", "message": "Доступ запрещен"}
                
                # Удаляем тему
                await db.execute("DELETE FROM topic WHERE id = ?", (topic_id,))
                await db.commit()
                
                self.logger.info(f"Удалена тема ID:{topic_id} пользователем {user_id}")
                return {"status": "success"}
        except Exception as e:
            self.logger.error(f"Ошибка удаления темы ID:{topic_id} пользователем {user_id}: {e}")
            return {"status": "error", "message": str(e)}

# Глобальные экземпляры
db_handler = DatabaseHandler()
topic_handler = TopicHandler()
