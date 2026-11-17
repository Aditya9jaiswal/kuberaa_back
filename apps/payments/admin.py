# apps/payments/admin.py
from django.contrib import admin
from apps.payments.models import (
    PaymentScreenshot, AdminReviewLog, FraudLog,
    AdminNotification, UserNotification
)


@admin.register(PaymentScreenshot)
class PaymentScreenshotAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'uploaded_by', 'amount', 'transaction_id',
        'status', 'fraud_score', 'uploaded_at'
    ]
    list_filter = ['status', 'payment_app', 'uploaded_at']
    search_fields = ['transaction_id', 'uploaded_by__username', 'user_upi_id']
    readonly_fields = ['fraud_score', 'fraud_flags']
    # ✅ file_hash aur perceptual_hash hata diye
    # ✅ payer_upi_id → user_upi_id kar diya


@admin.register(AdminReviewLog)
class AdminReviewLogAdmin(admin.ModelAdmin):
    list_display = ['screenshot', 'admin', 'action', 'created_at']
    list_filter = ['action', 'created_at']


@admin.register(FraudLog)
class FraudLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'reason', 'ip_address', 'created_at']
    list_filter = ['reason', 'created_at']
    search_fields = ['user__username', 'reason']


@admin.register(AdminNotification)
class AdminNotificationAdmin(admin.ModelAdmin):
    list_display = ['id', 'target_admin', 'priority', 'title', 'is_read', 'is_actioned', 'created_at']
    list_filter = ['priority', 'type', 'is_read', 'is_actioned']
    search_fields = ['title', 'message']


@admin.register(UserNotification)
class UserNotificationAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'title', 'is_read', 'created_at']
    list_filter = ['is_read', 'type']
    search_fields = ['title', 'user__username']