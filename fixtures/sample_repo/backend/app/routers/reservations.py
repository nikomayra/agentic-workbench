from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db

router = APIRouter(prefix="/reservations", tags=["reservations"])


@router.post("", response_model=schemas.ReservationOut, status_code=201)
def create_reservation(data: schemas.ReservationCreate, db: Session = Depends(get_db)):
    return crud.create_reservation(db, data)


@router.get("", response_model=list[schemas.ReservationOut])
def list_reservations(db: Session = Depends(get_db)):
    return crud.list_reservations(db)


@router.get("/{reservation_id}", response_model=schemas.ReservationOut)
def get_reservation(reservation_id: int, db: Session = Depends(get_db)):
    reservation = crud.get_reservation(db, reservation_id)
    if reservation is None:
        raise HTTPException(status_code=404, detail="Reservation not found")
    return reservation


@router.patch("/{reservation_id}", response_model=schemas.ReservationOut)
def update_reservation(
    reservation_id: int, data: schemas.ReservationUpdate, db: Session = Depends(get_db)
):
    reservation = crud.get_reservation(db, reservation_id)
    if reservation is None:
        raise HTTPException(status_code=404, detail="Reservation not found")
    return crud.update_status(db, reservation, data.status)


@router.delete("/{reservation_id}", status_code=204)
def delete_reservation(reservation_id: int, db: Session = Depends(get_db)):
    reservation = crud.get_reservation(db, reservation_id)
    if reservation is None:
        raise HTTPException(status_code=404, detail="Reservation not found")
    crud.delete_reservation(db, reservation)
