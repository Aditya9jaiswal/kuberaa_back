import logging
from typing import Dict, Optional

from .client import get_firestore_client, get_messaging

logger = logging.getLogger(__name__)


class FCMService:
    @staticmethod
    def send_to_token(token: str, title: str, body: str, data: Optional[Dict] = None) -> bool:
        try:
            messaging = get_messaging()
            message = messaging.Message(
                notification=messaging.Notification(title=title, body=body),
                data={k: str(v) for k, v in (data or {}).items()},
                token=token,
            )
            messaging.send(message)
            return True
        except Exception as e:
            logger.exception(f"FCM send failed: {e}")
            return False

    @staticmethod
    def send_to_user(user_id: str, title: str, body: str, data: Optional[Dict] = None) -> bool:
        db = get_firestore_client()
        doc = db.collection('users').document(user_id).get()
        if not doc.exists:
            return False
        token = doc.to_dict().get('fcmToken')
        if not token:
            return False
        return FCMService.send_to_token(token, title, body, data)