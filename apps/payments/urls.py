# apps/payments/urls.py
from django.urls import path
from apps.payments import views

app_name = 'payments'

urlpatterns = [
    # ✅ User
    path('extract-utr/', views.ExtractUtrView.as_view(), name='extract-utr'),
    path('submit-payment/', views.SubmitPaymentView.as_view(), name='submit-payment'),
    path('check-utr/', views.CheckUtrView.as_view(), name='check-utr'),
    path('my-payments/', views.MyUploadsView.as_view(), name='my-payments'),
    path('fraud-status/', views.FraudStatusView.as_view(), name='fraud-status'),
    path('upi-links/<uuid:tournament_id>/', views.UpiLinksView.as_view(), name='upi-links'),

    # ✅ Admin
    path('admin/review-queue/', views.AdminReviewQueueView.as_view(), name='admin-review-queue'),
    path('admin/review-decision/<int:pk>/', views.AdminReviewDecisionView.as_view(), name='admin-review-decision'),
    path('admin/notifications/', views.AdminNotificationListView.as_view(), name='admin-notifications'),
    path('admin/notifications/unread-count/', views.AdminNotificationUnreadCountView.as_view(), name='admin-notif-unread'),
    path('admin/notifications/read/<int:pk>/', views.AdminNotificationReadView.as_view(), name='admin-notif-read'),
    path('admin/notifications/read-all/', views.AdminNotificationReadAllView.as_view(), name='admin-notif-read-all'),

    # ✅ User notifications
    path('notifications/', views.UserNotificationListView.as_view(), name='user-notifications'),
]