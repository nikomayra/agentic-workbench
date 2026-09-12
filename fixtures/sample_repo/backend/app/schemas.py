from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class ReservationStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


class ReservationCreate(BaseModel):
    guest_name: str
    property_id: str
    check_in: datetime
    check_out: datetime


class ReservationUpdate(BaseModel):
    status: ReservationStatus


class ReservationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    guest_name: str
    property_id: str
    check_in: datetime
    check_out: datetime
    status: ReservationStatus
    created_at: datetime
