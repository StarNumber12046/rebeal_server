import base64
import json
import os
from fastapi import FastAPI, Form
from enum import StrEnum
from sqlalchemy import create_engine, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session
from pydantic import BaseModel
import dotenv
import firebase_admin
from firebase_admin import messaging, credentials
from firebase_admin.exceptions import FirebaseError

dotenv.load_dotenv(".env")

# Firebase Admin SDK initialization
cred = credentials.Certificate(json.loads(base64.b64decode(os.environ["FIREBASE_ADMIN_CREDENTIALS"]).decode("utf-8")))
firebase_admin.initialize_app(cred)

CONNECTION_STRING = os.environ["POSTGRES_URL"] if os.environ["POSTGRES_URL"].startswith("postgresql://") else "postgresql" + os.environ["POSTGRES_URL"].removeprefix("postgres")
CONNECTION_STRING = os.environ["POSTGRES_URL"] if os.environ["POSTGRES_URL"].startswith("sqlite://") else CONNECTION_STRING


class Base(DeclarativeBase):
    pass

class Region(StrEnum):
    us_central = "us-central"
    europe_west = "europe-west"
    asia_west = "asia-west"
    asia_east = "asia-east"

class RegistrationTicket(BaseModel):
    region: Region
    fcmToken: str  # Use FCM token instead of expoToken

class RegionPayload(BaseModel):
    region: Region

class Notifications(Base):
    __tablename__ = "notifications"
    notification_token: Mapped[str] = mapped_column(String, primary_key=True)
    region: Mapped[Region] = mapped_column(String)
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    def __repr__(self) -> str:
        return f"Notification(notification_token={self.notification_token}, region={self.region}, id={self.id});"

# Create database engine
engine = create_engine(CONNECTION_STRING, echo=True)
Notifications.metadata.create_all(engine)

app = FastAPI()

@app.post("/register")
def register_notifications(registration: RegistrationTicket):
    print(registration)
    fcm_token = registration.fcmToken
    region = registration.region
    with Session(engine) as session:
        notification = Notifications(notification_token=fcm_token, region=region)
        session.add(notification)
        session.commit()
        return {"status": "ok"}

@app.post("/notify")
def notify(region: Region = Form(...)) -> dict[str, str|int]:
    print(region)
    success = 0
    fail = 0
    with Session(engine) as session:
        notifications = session.query(Notifications).filter(Notifications.region == region).all()
        for notification in notifications:
            try:
                # Create message object with token
                message = messaging.Message(
                    data={"type": "moment"},
                    token=notification.notification_token  # Include the target token
                )
                # Send message via FCM
                response = messaging.send(message)
                print(f"Successfully sent message: {response}")
                success += 1
            except FirebaseError as e:
                # Log Firebase error details
                print(f"Error sending FCM notification to {notification.notification_token}: {str(e)}")
                fail += 1
            except Exception as e:
                # Catch any other unforeseen errors
                print(f"Unexpected error: {str(e)}")
                fail += 1

    return {"status": "ok", "success": success, "fail": fail}
