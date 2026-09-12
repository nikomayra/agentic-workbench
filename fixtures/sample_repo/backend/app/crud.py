from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, schemas


def create_reservation(db: Session, data: schemas.ReservationCreate) -> models.Reservation:
    reservation = models.Reservation(**data.model_dump())
    db.add(reservation)
    db.commit()
    db.refresh(reservation)
    return reservation


def list_reservations(db: Session) -> list[models.Reservation]:
    return list(db.scalars(select(models.Reservation)))


def get_reservation(db: Session, reservation_id: int) -> models.Reservation | None:
    return db.get(models.Reservation, reservation_id)


def update_status(
    db: Session, reservation: models.Reservation, status: schemas.ReservationStatus
) -> models.Reservation:
    reservation.status = status
    db.commit()
    db.refresh(reservation)
    return reservation


def delete_reservation(db: Session, reservation: models.Reservation) -> None:
    db.delete(reservation)
    db.commit()
