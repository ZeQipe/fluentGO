import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime
import pytz

from services.cron_tasks import (
    cleanup_guest_users_task,
    process_subscription_payments_task,
    grant_free_minutes_task,
    cleanup_payments_storage_task,
    retry_on_error
)
from services.cron_manager import cron_logger

# Московская timezone
MOSCOW_TZ = pytz.timezone('Europe/Moscow')

class CronScheduler:
    """Планировщик кронтабов"""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone=MOSCOW_TZ)
        self.is_running = False
    
    def setup_jobs(self):
        """Настройка всех кронтабов"""
        
        # ========================================
        # КРОНТАБ 1: Удаление гостевых пользователей
        # Запуск: 1 число каждого месяца в 03:00 МСК
        # ========================================
        self.scheduler.add_job(
            func=lambda: retry_on_error(cleanup_guest_users_task, "cleanup_guest_users"),
            trigger=CronTrigger(day=1, hour=3, minute=0, timezone=MOSCOW_TZ),
            id='cleanup_guests',
            name='Удаление гостевых пользователей',
            replace_existing=True
        )
        
        # ========================================
        # КРОНТАБ 2: Запрос автоплатежей
        # Запуск: каждый день в 04:00 МСК
        # ========================================
        self.scheduler.add_job(
            func=lambda: retry_on_error(process_subscription_payments_task, "subscription_payments"),
            trigger=CronTrigger(hour=4, minute=0, timezone=MOSCOW_TZ),
            id='subscription_payments',
            name='Запрос автоплатежей',
            replace_existing=True
        )
        
        # ========================================
        # КРОНТАБ 3: Начисление 2 минут
        # Запуск: 1 число каждого месяца в 05:00 МСК
        # ========================================
        self.scheduler.add_job(
            func=lambda: retry_on_error(grant_free_minutes_task, "grant_free_minutes"),
            trigger=CronTrigger(day=1, hour=5, minute=0, timezone=MOSCOW_TZ),
            id='grant_free_minutes',
            name='Начисление 2 минут авторизованным',
            replace_existing=True
        )
        
        # ========================================
        # КРОНТАБ 4: Очистка хранилища платежей
        # Запуск: каждый час
        # ========================================
        self.scheduler.add_job(
            func=lambda: retry_on_error(cleanup_payments_storage_task, "cleanup_payments"),
            trigger=IntervalTrigger(hours=1, timezone=MOSCOW_TZ),
            id='cleanup_payments',
            name='Очистка хранилища платежей',
            replace_existing=True
        )
        
        cron_logger.log("scheduler", "INFO", "Все кронтабы настроены", {
            "jobs_count": len(self.scheduler.get_jobs()),
            "timezone": str(MOSCOW_TZ)
        })
    
    def start(self):
        """Запуск планировщика"""
        if not self.is_running:
            self.scheduler.start()
            self.is_running = True
            cron_logger.log("scheduler", "INFO", "Планировщик кронтабов запущен")
            
            # Выводим список задач
            jobs = self.scheduler.get_jobs()
            for job in jobs:
                next_run = job.next_run_time.strftime('%Y-%m-%d %H:%M:%S') if job.next_run_time else 'N/A'
                cron_logger.log("scheduler", "INFO", f"Задача: {job.name}, следующий запуск: {next_run}")
    
    def stop(self):
        """Остановка планировщика"""
        if self.is_running:
            self.scheduler.shutdown()
            self.is_running = False
            cron_logger.log("scheduler", "INFO", "Планировщик кронтабов остановлен")

# Глобальный экземпляр планировщика
cron_scheduler = CronScheduler()

