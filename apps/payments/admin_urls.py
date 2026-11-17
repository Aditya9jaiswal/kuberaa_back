# apps/payments/admin_urls.py
from django.urls import path
from apps.payments import admin_views

app_name = 'payments_admin'

urlpatterns = [
    path('reviews/', admin_views.AdminReviewQueueView.as_view(), name='reviews'),
    path('reviews/<int:pk>/', admin_views.AdminReviewDetailView.as_view(), name='review-detail'),
    path('reviews/<int:pk>/decision/', admin_views.AdminReviewDecisionView.as_view(), name='review-decision'),
    path('reviews/bulk/', admin_views.AdminBulkDecisionView.as_view(), name='bulk'),
    
    path('notifications/', admin_views.AdminNotificationListView.as_view(), name='notifications'),
    path('notifications/unread-count/', admin_views.AdminNotificationUnreadCountView.as_view(), name='unread-count'),
    path('notifications/<int:pk>/read/', admin_views.AdminNotificationReadView.as_view(), name='notification-read'),
    path('notifications/read-all/', admin_views.AdminNotificationReadAllView.as_view(), name='notifications-read-all'),
    
    path('user-notifications/', admin_views.UserNotificationListView.as_view(), name='user-notifications'),
]