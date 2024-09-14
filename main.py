import os
from fastapi import Body, FastAPI, Form
from enum import StrEnum
from sqlalchemy import create_engine
from pydantic import BaseModel
from sqlalchemy import String
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import Session
import json
import requests
import dotenv
from requests.exceptions import ConnectionError, HTTPError
from exponent_server_sdk import (
    PushClient,
    PushServerError,
    PushMessage,
)

dotenv.load_dotenv(".env")

CONNECTION_STRING = os.environ["POSTGRES_URL"] if os.environ["POSTGRES_URL"].startswith("postgresql://") else "postgresql" + os.environ["POSTGRES_URL"].removeprefix("postgres")

expo_session = requests.Session()
expo_session.headers.update(
    {
        "accept": "application/json",
        "accept-encoding": "gzip, deflate",
        "content-type": "application/json",
    }
)


class Base(DeclarativeBase):
    pass

class Region(StrEnum):
    us_central = "us-central"
    europe_west = "europe-west"
    asia_west = "asia-west"
    asia_east = "asia-east"


class RegistrationTicket(BaseModel):
    region: Region
    expoToken: str

class RegionPayload(BaseModel):
    region: Region

class Notifications(Base):
    __tablename__ = "notifications"
    notification_token: Mapped[str] = mapped_column(String)
    region: Mapped[Region] = mapped_column(String)
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    def __repr__(self) -> str:
        return f"Notification(notification_token={self.notification_token}, region={self.region}, id={self.id})"

engine = create_engine(CONNECTION_STRING, echo=True)
Notifications.metadata.create_all(engine)

app = FastAPI()

@app.post("/register")
def register_notifications(registration: RegistrationTicket):
    print(registration)
    expo_token = registration.expoToken
    region = registration.region
    with Session(engine) as session:
        notification = Notifications(notification_token=expo_token, region=region)
        session.add(notification)
        session.commit()
        return {"status": "ok"}
@app.post("/notify")
def notify(region: Region = Form(...)):
    print(region)
    success = 0
    fail = 0
    with Session(engine) as session:
        notifications = session.query(Notifications).filter(Notifications.region == region).all()
        for notification in notifications:
            try:
                PushClient(session=expo_session).publish(
                    PushMessage(
                        to=notification.notification_token,
                        title="⚠️ It's time to BeReal! ⚠️",
                        body="You have two minutes to post a ReBeal!",
                    )
                )
                success += 1
            except PushServerError as e:
                # Log more details about the error
                print(f"Error sending push notification to {notification.notification_token}: {str(e)}")
                fail += 1
            except Exception as e:
                # Catch any other unforeseen errors
                print(f"Unexpected error: {str(e)}")
                fail += 1

    return {"status": "ok", "success": success, "fail": fail}
