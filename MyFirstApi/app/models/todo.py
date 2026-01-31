from app.database import db
from datetime import datetime, timezone


class TodoModel(db.Model):
    __tablename__ = "todos"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(30), unique=True, nullable=False)
    task = db.Column(db.String(255), unique=True, nullable=False)
    done = db.Column(db.Boolean, default=False)
    created_at = db.Column(
            db.DateTime, default=lambda: datetime.now(timezone.utc)
        )
