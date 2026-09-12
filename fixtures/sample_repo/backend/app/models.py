from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Reservation(Base):
    __tablename__ = "reservations"

    id: Mapped[int] = mapped_column(primary_key=True)
    guest_name: Mapped[str]
    property_id: Mapped[str]
    check_in: Mapped[datetime]
    check_out: Mapped[datetime]
    status: Mapped[str] = mapped_column(default="pending")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
