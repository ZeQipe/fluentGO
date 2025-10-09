from fastapi import APIRouter, HTTPException
from database import db_handler
from pydantic import BaseModel
from typing import Optional
import json

router = APIRouter()

# Модель для CRM создания пользователя
class CreateUserRequest(BaseModel):
    id: str
    user_name: str
    email: str
    remaining_seconds: Optional[int] = 0
    permanent_seconds: Optional[int] = 0
    tariff: Optional[str] = "free"
    payment_status: Optional[str] = "unpaid"
    payment_date: Optional[int] = None
    status: Optional[str] = "user"
    iat: Optional[int] = None
    exp: Optional[int] = None

# Модель для CRM обновления баланса пользователя
class UpdateUserBalanceRequest(BaseModel):
    add_remaining_seconds: Optional[int] = None
    add_monthly_seconds: Optional[int] = None
    tariff: Optional[str] = None
    payment_status: Optional[str] = None

# Модель для смены статуса пользователя
class UpdateUserStatusRequest(BaseModel):
    status: str

@router.get("/api/tariffs")
async def get_crm_tariffs():
    """CRM: Получение списка тарифов"""
    try:
        # Загружаем тарифы из файла
        with open("document/tariffs.json", "r", encoding="utf-8") as f:
            tariffs_data = json.load(f)
        
        return {
            "status": "success",
            "tariffs": tariffs_data
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Ошибка получения тарифов: {str(e)}"
        }

@router.post("/api/user")
async def create_crm_user(user_data: CreateUserRequest):
    """CRM: Создание нового пользователя"""
    try:
        # Проверяем, существует ли пользователь
        existing_user = await db_handler.get_user(user_data.id)
        if existing_user:
            raise HTTPException(status_code=409, detail="Пользователь с таким ID уже существует")
        
        # Создаем пользователя
        success = await db_handler.create_user(
            user_id=user_data.id,
            user_name=user_data.user_name,
            email=user_data.email,
            remaining_seconds=user_data.remaining_seconds,
            permanent_seconds=user_data.permanent_seconds,
            tariff=user_data.tariff,
            payment_status=user_data.payment_status,
            payment_date=user_data.payment_date,
            status=user_data.status,
            iat=user_data.iat,
            exp=user_data.exp
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Ошибка создания пользователя")
        
        # Получаем созданного пользователя
        created_user = await db_handler.get_user(user_data.id)
        
        return {
            "status": "success",
            "message": "Пользователь успешно создан",
            "data": {
                "user_id": created_user["id"],
                "user_name": created_user["user_name"],
                "email": created_user["email"],
                "remaining_seconds": created_user.get("remaining_seconds", 0),
                "permanent_seconds": created_user.get("permanent_seconds", 0),
                "tariff": created_user.get("tariff", "free"),
                "payment_status": created_user.get("payment_status", "unpaid"),
                "payment_date": created_user.get("payment_date"),
                "status": created_user.get("status", "user")
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        return {
            "status": "error",
            "message": f"Ошибка создания пользователя: {str(e)}"
        }

@router.get("/api/user/{user_id}/balance")
async def get_crm_user_balance(user_id: str):
    """CRM: Получение баланса конкретного пользователя"""
    try:
        # Получаем пользователя из БД
        user = await db_handler.get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        return {
            "status": "success",
            "data": {
                "user_id": user["id"],
                "user_name": user["user_name"],
                "remaining_seconds": user.get("remaining_seconds", 0),
                "monthly_seconds": 0,  # TODO: добавить поле в БД если нужно
                "tariff": user.get("tariff", "free"),
                "payment_status": user.get("payment_status", "unpaid")
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        return {
            "status": "error", 
            "message": f"Ошибка получения баланса: {str(e)}"
        }

@router.put("/api/user/{user_id}/balance")
async def update_crm_user_balance(user_id: str, balance_data: UpdateUserBalanceRequest):
    """CRM: Обновление баланса пользователя"""
    try:
        # Проверяем существование пользователя
        user = await db_handler.get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        updates = {}
        
        # Обрабатываем начисление несгораемых секунд
        if balance_data.add_remaining_seconds is not None:
            current_seconds = user.get("remaining_seconds", 0)
            new_seconds = current_seconds + balance_data.add_remaining_seconds
            updates['remaining_seconds'] = max(0, new_seconds)
        
        # TODO: Обрабатываем начисление месячных секунд (когда добавим поле в БД)
        # if balance_data.add_monthly_seconds is not None:
        #     current_monthly = user.get("monthly_seconds", 0)
        #     new_monthly = current_monthly + balance_data.add_monthly_seconds
        #     updates['monthly_seconds'] = max(0, new_monthly)
        
        # Обрабатываем смену тарифа
        if balance_data.tariff is not None:
            updates['tariff'] = balance_data.tariff
            
        # Обрабатываем статус оплаты
        if balance_data.payment_status is not None:
            updates['payment_status'] = balance_data.payment_status
        
        # Применяем изменения если есть что обновлять
        if updates:
            success = await db_handler.update_user(user_id, **updates)
            if not success:
                raise HTTPException(status_code=500, detail="Ошибка обновления данных")
        
        # Возвращаем обновленные данные
        updated_user = await db_handler.get_user(user_id)
        
        return {
            "status": "success",
            "message": "Баланс обновлен",
            "data": {
                "user_id": updated_user["id"],
                "user_name": updated_user["user_name"],
                "remaining_seconds": updated_user.get("remaining_seconds", 0),
                "monthly_seconds": 0,  # TODO: когда добавим поле в БД
                "tariff": updated_user.get("tariff", "free"),
                "payment_status": updated_user.get("payment_status", "unpaid")
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        return {
            "status": "error",
            "message": f"Ошибка обновления баланса: {str(e)}"
        }

@router.put("/api/user/{user_id}/status")
async def update_crm_user_status(user_id: str, status_data: UpdateUserStatusRequest):
    """CRM: Изменение статуса пользователя"""
    try:
        # Проверяем существование пользователя
        user = await db_handler.get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        # Обновляем статус
        success = await db_handler.update_user(user_id, status=status_data.status)
        if not success:
            raise HTTPException(status_code=500, detail="Ошибка обновления статуса")
        
        # Получаем обновленного пользователя
        updated_user = await db_handler.get_user(user_id)
        
        return {
            "status": "success",
            "message": f"Статус пользователя изменен на '{status_data.status}'",
            "data": {
                "user_id": updated_user["id"],
                "user_name": updated_user["user_name"],
                "status": updated_user.get("status", "user"),
                "email": updated_user.get("email"),
                "tariff": updated_user.get("tariff", "free"),
                "payment_status": updated_user.get("payment_status", "unpaid")
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        return {
            "status": "error",
            "message": f"Ошибка изменения статуса: {str(e)}"
        }
