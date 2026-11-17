# apps/payments/serializers.py
from rest_framework import serializers
from apps.payments.models import (
    PaymentScreenshot, AdminNotification, UserNotification
)


class PaymentScreenshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentScreenshot
        fields = [
            'id', 'status', 'transaction_id', 'amount',
            'payment_date', 'payment_app', 'fraud_score',
            'uploaded_at', 'rejection_reason', 'admin_notes',
        ]
        read_only_fields = fields


class AdminNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdminNotification
        fields = [
            'id', 'type', 'priority', 'title', 'message',
            'screenshot_id', 'is_read', 'metadata', 'created_at',
        ]


class UserNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserNotification
        fields = [
            'id', 'type', 'title', 'message',
            'screenshot_id', 'is_read', 'created_at',
        ]