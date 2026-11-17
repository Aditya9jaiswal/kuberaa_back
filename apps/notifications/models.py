from django.db import models
from django.utils import timezone
from datetime import timedelta
import uuid


class Notification(models.Model):
    class Type(models.TextChoices):
        # Payment
        PAYMENT_SUBMITTED = 'payment_submitted', 'Payment Submitted'
        PAYMENT_VERIFIED = 'payment_verified', 'Payment Verified'
        PAYMENT_REJECTED = 'payment_rejected', 'Payment Rejected'

        # Tournament
        TOURNAMENT_REGISTERED = 'tournament_registered', 'Tournament Registered'
        TOURNAMENT_CANCELLED = 'tournament_cancelled', 'Tournament Cancelled'

        # Match / Room
        MATCH_START = 'match_start', 'Match Start'
        ROOM_RELEASED = 'room_released', 'Room Released'
        CAN_PLAY_APPROVED = 'can_play_approved', 'Can Play Approved'

        # Results
        RESULT_PUBLISHED = 'result_published', 'Result Published'
        WINNING = 'winning', 'Winning'
        PRIZE_PAID = 'prize_paid', 'Prize Paid'

        # Admin Actions
        ACCOUNT_BLOCKED = 'account_blocked', 'Account Blocked'
        ACCOUNT_SUSPENDED = 'account_suspended', 'Account Suspended'
        FRAUD_WARNING = 'fraud_warning', 'Fraud Warning'

        # System
        SYSTEM = 'system', 'System'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    title = models.CharField(max_length=200)
    body = models.TextField()
    notification_type = models.CharField(
        max_length=32,
        choices=Type.choices,
        default=Type.SYSTEM,
        db_index=True,
    )
    tournament_id = models.UUIDField(null=True, blank=True)
    match_id = models.UUIDField(null=True, blank=True)
    data = models.JSONField(default=dict, blank=True)
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    # ✅ Auto-delete after 7 days
    expires_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        help_text='Auto-delete after this time',
    )

    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['expires_at']),
        ]

    def save(self, *args, **kwargs):
        # ✅ Pehli baar save hone pe 7 din baad expire
        if not self.pk:
            self.expires_at = timezone.now() + timedelta(days=7)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.email} - {self.title}"


# Alias for backward compatibility
UserNotification = Notification