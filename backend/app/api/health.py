from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_async_db_session

router = APIRouter()


@router.get("/health")
async def health(db: AsyncSession = Depends(get_async_db_session)) -> dict:
    try:
        await db.execute(text("SELECT 1"))
        db_status = "ok"
    except SQLAlchemyError:
        db_status = "unreachable"

    return {
        "status": "ok",
        "database": db_status,
    }
