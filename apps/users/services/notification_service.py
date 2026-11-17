# apps/users/services/notification_service.py

from apps.payments.models import UserNotification

class NotificationService:
    # ... existing methods ...

    @staticmethod
    def create_notification(user, title, message, type='system', data=None):
        """
        Database me notification create karega.
        """
        try:
            notification = UserNotification.objects.create(
                user=user,
                title=title,
                message=message,
                type=type,
                data=data or {},
            )
            return notification
        except Exception as e:
            print(f"❌ DB Notification error for {user.email}: {e}")
            return None