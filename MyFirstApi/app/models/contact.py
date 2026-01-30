from app.database import db
from datetime import datetime, timezone


class ContactModel(db.Model):
    __tablename__ = "contacts"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(30), nullable=False)
    email = db.Column(db.String(50), unique=True, nullable=False)
    phone = db.Column(db.String(10), unique=True, nullable=False)
    address = db.Column(db.String(100), nullable=True, default="Unknown")
    city = db.Column(db.String(30), nullable=True, default="Unknown")
    state = db.Column(db.String(20), nullable=True, default="Unknown")
    zip = db.Column(db.String(8), nullable=True, default="Unknown")
    country = db.Column(db.String(30), nullable=False, default="Unknown")
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )
