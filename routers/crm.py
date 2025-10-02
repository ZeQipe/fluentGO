from fastapi import APIRouter, HTTPException
from database import db_handler
from pydantic import BaseModel
from typing import Optional
import json

router = APIRouter()

# Модель для CRM обновления баланса пользователя
class UpdateUserBalanceRequest(BaseModel):
    add_remaining_seconds: Optional[int] = None
    add_monthly_seconds: Optional[int] = None
    tariff: Optional[str] = None
    payment_status: Optional[str] = None

@router.get("/api/tariffs")
async def get_crm_tariffs():
    """CRM: Получение списка тарифов"""
    try:
        # Загружаем тарифы из файла
        with open("tariffs.json", "r", encoding="utf-8") as f:
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
