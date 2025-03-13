from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from app.models.bus_route import BusRoute

router = APIRouter()

@router.get("/notifications")
def get_notifications(db: Session = Depends(get_db)):
    """Fetch all notifications."""
    return db.query(BusRoute).all()

@router.put("/notifications/{notification_id}/read")
def mark_notification_as_read(notification_id: int, db: Session = Depends(get_db)):
    """Mark a notification as read."""
    notification = db.query(BusRoute).filter(BusRoute.id == notification_id).first()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    notification.read = True
    db.commit()
    return {"message": "Notification marked as read"}
