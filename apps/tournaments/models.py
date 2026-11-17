# apps/tournaments/models.py

from django.db import models
from django.utils import timezone
import uuid


class Tournament(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        OPEN = 'OPEN', 'Open'
        FULL = 'FULL', 'Full'
        REGISTRATION_CLOSED = 'REGISTRATION_CLOSED', 'Registration Closed'
        UPCOMING = 'UPCOMING', 'Upcoming'
        LIVE = 'LIVE', 'Live'
        COMPLETED = 'COMPLETED', 'Completed'
        CANCELLED = 'CANCELLED', 'Cancelled'

    class TournamentType(models.TextChoices):
        BGMI = 'BGMI', 'BGMI'
        FREEFIRE = 'FREEFIRE', 'Free Fire'
        COD = 'COD', 'Call of Duty'
        VALORANT = 'VALORANT', 'Valorant'
        PUBG = 'PUBG', 'PUBG'
        OTHER = 'OTHER', 'Other'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    serial_number = models.PositiveIntegerField(
        unique=True, editable=False, db_index=True,
        null=True, blank=True,
    )

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    rules = models.TextField(blank=True)
    prize_info = models.TextField(blank=True)

    tournament_type = models.CharField(
        max_length=20,
        choices=TournamentType.choices,
        default=TournamentType.OTHER,
        db_index=True,
        help_text='Game type — app mein image select karne ke liye',
    )

    tournament_date = models.DateField()
    start_time = models.DateTimeField()
    registration_start = models.DateTimeField()
    registration_end = models.DateTimeField()

    maximum_participants = models.PositiveIntegerField(default=100)
    current_participants = models.PositiveIntegerField(default=0)

    entry_fee = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text='Entry fee amount (₹)'
    )
    upi_id = models.CharField(max_length=100, blank=True)
    upi_name = models.CharField(max_length=120, blank=True)

    status = models.CharField(
        max_length=32, choices=Status.choices,
        default=Status.DRAFT, db_index=True,
    )

    created_by = models.ForeignKey(
        'users.User', on_delete=models.SET_NULL, null=True,
        related_name='created_tournaments',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tournaments'
        ordering = ['-serial_number']
        indexes = [
            models.Index(fields=['status', 'start_time']),
            models.Index(fields=['serial_number']),
        ]

    def save(self, *args, **kwargs):
        if not self.serial_number:
            last = Tournament.objects.order_by('-serial_number').first()
            if last and last.serial_number:
                self.serial_number = last.serial_number + 1
            else:
                self.serial_number = 1
        super().save(*args, **kwargs)

    def __str__(self):
        return f"#{self.display_id} {self.title} ({self.status})"

    @property
    def display_id(self):
        if self.serial_number is None:
            return "0000"
        return f"{self.serial_number:04d}"

    @property
    def is_registration_open(self):
        now = timezone.now()
        return (
            self.status == self.Status.OPEN
            and self.registration_start <= now <= self.registration_end
            and self.current_participants < self.maximum_participants
        )

    @property
    def is_full(self):
        return self.current_participants >= self.maximum_participants

    @property
    def slots_left(self):
        return max(0, self.maximum_participants - self.current_participants)

    # ═══════════════════════════════════════════════════════════
    # ✅ KUBERAA POINTS PROPERTIES (NAYE)
    # ═══════════════════════════════════════════════════════════
    @property
    def is_first_free_eligible(self):
        """₹10 wala match hai — first free eligible?"""
        return float(self.entry_fee) == 10.0


# ═══════════════════════════════════════════════════════════
# Registration — UPDATED with Kuberaa Points
# ═══════════════════════════════════════════════════════════

class Registration(models.Model):
    class Status(models.TextChoices):
        PENDING_PAYMENT = 'PENDING_PAYMENT', 'Pending Payment'
        PAYMENT_SUBMITTED = 'PAYMENT_SUBMITTED', 'Payment Submitted'
        CONFIRMED = 'CONFIRMED', 'Confirmed'
        PAYMENT_REJECTED = 'PAYMENT_REJECTED', 'Payment Rejected'
        CANCELLED = 'CANCELLED', 'Cancelled'
        FREE_ENTRY_PENDING = 'FREE_ENTRY_PENDING', 'Free Entry Pending'

    # ✅ NAYA: Payment Type
    class PaymentType(models.TextChoices):
        CASH = 'CASH', 'Cash Payment'
        POINTS = 'POINTS', 'Kuberaa Points'
        FIRST_FREE = 'FIRST_FREE', 'First Match Free'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tournament = models.ForeignKey(
        Tournament, on_delete=models.CASCADE, related_name='registrations',
    )
    user = models.ForeignKey(
        'users.User', on_delete=models.CASCADE, related_name='registrations',
    )

    free_fire_uid = models.CharField(max_length=64, db_index=True)
    free_fire_name = models.CharField(max_length=120)

    user_upi_id = models.CharField(
        max_length=100, blank=True, default='',
        help_text='User UPI ID'
    )
    user_mobile = models.CharField(
        max_length=20, blank=True, default='',
        help_text='Contact mobile'
    )

    status = models.CharField(
        max_length=32, choices=Status.choices,
        default=Status.PENDING_PAYMENT, db_index=True,
    )

    can_play = models.BooleanField(
        default=False,
        help_text='Admin approved this player for match room'
    )

    # ✅ FREE ENTRY FIELDS
    is_free_entry = models.BooleanField(
        default=False,
        help_text='Ye registration free entry se hui hai',
    )
    entry_fee_paid = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text='Kitna entry fee pay kiya (free entry ke liye 0)',
    )

    # ═══════════════════════════════════════════════════════════
    # ✅ KUBERAA POINTS FIELDS (NAYE)
    # ═══════════════════════════════════════════════════════════
    points_used = models.IntegerField(
        default=0,
        help_text='Kitne Kuberaa Points use kiye',
    )
    is_first_free = models.BooleanField(
        default=False,
        help_text='Ye registration first free match hai',
    )
    payment_type = models.CharField(
        max_length=20,
        choices=PaymentType.choices,
        default=PaymentType.CASH,
        db_index=True,
        help_text='Payment method: CASH / POINTS / FIRST_FREE',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'registrations'
        unique_together = [('tournament', 'user')]
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tournament', 'free_fire_uid']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['tournament', 'status']),
            models.Index(fields=['is_free_entry']),
            models.Index(fields=['payment_type']),      # ✅ NAYA
            models.Index(fields=['is_first_free']),     # ✅ NAYA
        ]

    def __str__(self):
        return f"{self.user.email} → #{self.tournament.display_id} ({self.status})"

    @property
    def is_confirmed(self):
        return self.status == self.Status.CONFIRMED

    # ═══════════════════════════════════════════════════════════
    # ✅ KUBERAA POINTS PROPERTIES (NAYE)
    # ═══════════════════════════════════════════════════════════
    @property
    def is_points_payment(self):
        return self.payment_type == self.PaymentType.POINTS

    @property
    def is_first_free_payment(self):
        return self.payment_type == self.PaymentType.FIRST_FREE

    @property
    def is_cash_payment(self):
        return self.payment_type == self.PaymentType.CASH

    @property
    def payment_badge(self):
        """Admin panel ke liye badge text"""
        if self.is_first_free_payment:
            return '🆕 NEW USER — FIRST FREE'
        elif self.is_points_payment:
            return f'🎁 KUBERAA POINTS ({self.points_used} used)'
        return '💰 CASH PAYMENT'


class MatchRoom(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tournament = models.OneToOneField(
        Tournament, on_delete=models.CASCADE, related_name='match_room',
    )
    room_id = models.CharField(max_length=64, blank=True)
    room_password = models.CharField(max_length=64, blank=True)
    scheduled_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'match_rooms'

    def __str__(self):
        return f"Room for #{self.tournament.display_id}"


class PrizeConfig(models.Model):
    tournament = models.OneToOneField(
        Tournament,
        on_delete=models.CASCADE,
        related_name='prize_config'
    )
    per_kill_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text='Har kill ka amount (₹)'
    )
    first_place_bonus = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text='1st place bonus (₹)'
    )
    second_place_bonus = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text='2nd place bonus (₹)'
    )
    third_place_bonus = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text='3rd place bonus (₹)'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tournament_prize_config'
        verbose_name = 'Prize Config'
        verbose_name_plural = 'Prize Configs'

    def __str__(self):
        return f"PrizeConfig for {self.tournament.title}"