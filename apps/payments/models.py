# apps/payments/models.py
import hashlib
from decimal import Decimal

from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class PaymentScreenshot(models.Model):
    """User payment — UTR based verification. Screenshot save nahi hoga."""

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
        ('manual_review', 'Admin Review Pending'),
    ]

    # ✅ Image optional — backend save nahi karega
    image = models.ImageField(
        upload_to='payments/%Y/%m/',
        null=True,
        blank=True,
    )

    # ✅ UTR — PRIMARY
    transaction_id = models.CharField(max_length=50, db_index=True)

    # Amount
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # User info
    uploaded_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='uploads'
    )
    user_upi_id = models.CharField(max_length=200, blank=True, default='')
    user_mobile = models.CharField(max_length=15, blank=True, default='')

    # App detected
    payment_app = models.CharField(max_length=50, blank=True, default='')

    # References
    tournament_id = models.CharField(max_length=100, blank=True, default='', db_index=True)
    registration_id = models.CharField(max_length=100, blank=True, default='', db_index=True)
    match_id = models.CharField(max_length=100, blank=True, default='', db_index=True)

    # Fraud detection
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='manual_review'
    )
    fraud_score = models.IntegerField(default=0)
    fraud_flags = models.JSONField(default=list, blank=True)
    review_problems = models.JSONField(default=list, blank=True)

    # Admin review
    admin_reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reviewed_payments'
    )
    admin_reviewed_at = models.DateTimeField(null=True, blank=True)
    admin_decision = models.CharField(
        max_length=20, blank=True, default='',
        choices=[('accepted', 'Accepted'), ('rejected', 'Rejected')]
    )
    admin_notes = models.TextField(blank=True, default='')
    rejection_reason = models.TextField(blank=True, default='')

    # Timestamps
    uploaded_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        db_table = 'payment_screenshots'
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['transaction_id']),
            models.Index(fields=['tournament_id']),
            models.Index(fields=['registration_id']),
            models.Index(fields=['status', '-uploaded_at']),
        ]
        unique_together = [
            ['uploaded_by', 'transaction_id'],
        ]

    def __str__(self):
        return f"Payment #{self.id} - {self.uploaded_by.email} - UTR: {self.transaction_id}"


# ═══════════════════════════════════════════════════════════
# ADMIN REVIEW LOG
# ═══════════════════════════════════════════════════════════

class AdminReviewLog(models.Model):
    screenshot = models.ForeignKey(
        PaymentScreenshot, on_delete=models.CASCADE, related_name='review_logs'
    )
    admin = models.ForeignKey(User, on_delete=models.CASCADE)
    action = models.CharField(max_length=20)
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'admin_review_logs'
        ordering = ['-created_at']


# ═══════════════════════════════════════════════════════════
# FRAUD LOG
# ═══════════════════════════════════════════════════════════

class FraudLog(models.Model):
    screenshot = models.ForeignKey(
        PaymentScreenshot, on_delete=models.CASCADE, null=True, blank=True
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    reason = models.CharField(max_length=200)
    details = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'fraud_logs'
        ordering = ['-created_at']


# ═══════════════════════════════════════════════════════════
# ADMIN NOTIFICATION
# ═══════════════════════════════════════════════════════════

class AdminNotification(models.Model):
    TYPE_CHOICES = [
        ('review_needed', 'Review Needed'),
        ('fraud_alert', 'Fraud Alert'),
        ('user_reported', 'User Reported'),
        ('system', 'System'),
    ]
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]

    type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    title = models.CharField(max_length=200)
    message = models.TextField()

    screenshot = models.ForeignKey(
        PaymentScreenshot, on_delete=models.CASCADE,
        null=True, blank=True, related_name='admin_notifications'
    )
    triggered_by = models.ForeignKey(
        User, on_delete=models.CASCADE,
        null=True, blank=True, related_name='triggered_notifications'
    )
    target_admin = models.ForeignKey(
        User, on_delete=models.CASCADE,
        null=True, blank=True, related_name='admin_notifications'
    )

    is_read = models.BooleanField(default=False)
    is_actioned = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'admin_notifications'
        ordering = ['-created_at']


# ═══════════════════════════════════════════════════════════
# USER NOTIFICATION
# ═══════════════════════════════════════════════════════════

class UserNotification(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='payment_notifications'  # ✅ FIX — 'notifications' se change kiya
    )
    type = models.CharField(max_length=30)
    title = models.CharField(max_length=200)
    message = models.TextField()
    screenshot = models.ForeignKey(
        PaymentScreenshot, on_delete=models.CASCADE,
        null=True, blank=True
    )
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'user_notifications'
        ordering = ['-created_at']