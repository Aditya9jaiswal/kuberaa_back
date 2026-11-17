# apps/notifications/urls.py

from django.urls import path
from .views import (
    NotificationListView,
    NotificationUnreadCountView,
    NotificationMarkReadView,
    NotificationMarkAllReadView,
    NotificationDeleteView,
    NotificationDeleteAllView,
    AdminSendNotificationView,  # ✅ Naya
)

urlpatterns = [
    path('', NotificationListView.as_view(), name='notification-list'),
    path('unread-count/', NotificationUnreadCountView.as_view(), name='notification-unread-count'),
    path('mark-all-read/', NotificationMarkAllReadView.as_view(), name='notification-mark-all-read'),
    path('delete-all/', NotificationDeleteAllView.as_view(), name='notification-delete-all'),
    path('<uuid:notification_id>/read/', NotificationMarkReadView.as_view(), name='notification-mark-read'),
    path('<uuid:notification_id>/', NotificationDeleteView.as_view(), name='notification-delete'),
    
    # ✅ Admin Notification Route
    path('admin/send-notification/', AdminSendNotificationView.as_view(), name='admin-send-notification'),
]