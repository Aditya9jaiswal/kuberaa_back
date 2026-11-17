# apps/results/models.py
import uuid
from django.db import models

from apps.tournaments.models import PrizeConfig


class Result(models.Model):
    class VerificationStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        VERIFIED = 'VERIFIED', 'Verified'
        PUBLISHED = 'PUBLISHED', 'Published'
        REJECTED = 'REJECTED', 'Rejected'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # ═══════════════════════════════════════════════════════
    # RELATIONS
    # ═══════════════════════════════════════════════════════
    match = models.ForeignKey(
        'matches.Match',
        on_delete=models.CASCADE,
        related_name='results',
        null=True, blank=True,
    )
    user = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='results',
    )

    # ═══════════════════════════════════════════════════════
    # PLAYER INFO
    # ═══════════════════════════════════════════════════════
    free_fire_uid = models.CharField(max_length=64, db_index=True)
    player_name = models.CharField(max_length=120)

    # ═══════════════════════════════════════════════════════
    # MATCH STATS
    # ═══════════════════════════════════════════════════════
    kills = models.PositiveIntegerField(default=0)
    placement = models.PositiveIntegerField(default=0)
    score = models.PositiveIntegerField(default=0)

    # ═══════════════════════════════════════════════════════
    # ✅ KUBERAA POINTS EARNED (NAYA)
    # ═══════════════════════════════════════════════════════
    points_earned = models.IntegerField(
        default=0,
        help_text='0 kill pe kitne Kuberaa Points mile',
    )

    # ═══════════════════════════════════════════════════════
    # ✅ PRIZE CALCULATION
    # ═══════════════════════════════════════════════════════
    prize_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
    )
    per_kill_prize = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text='Entry fee × 0.75 (per kill prize)',
    )
    entry_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text='Tournament entry fee at time of result',
    )

    # ═══════════════════════════════════════════════════════
    # PAYMENT
    # ═══════════════════════════════════════════════════════
    is_paid = models.BooleanField(default=False)
    paid_at = models.DateTimeField(null=True, blank=True)

    # ═══════════════════════════════════════════════════════
    # SCREENSHOT + OCR
    # ═══════════════════════════════════════════════════════
    screenshot = models.ImageField(
        upload_to='results/screenshots/', blank=True, null=True,
    )
    ocr_raw_text = models.TextField(blank=True)
    ocr_confidence = models.FloatField(default=0.0)

    # ═══════════════════════════════════════════════════════
    # VERIFICATION
    # ═══════════════════════════════════════════════════════
    verification_status = models.CharField(
        max_length=16,
        choices=VerificationStatus.choices,
        default=VerificationStatus.PENDING,
        db_index=True,
    )
    verified_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='verified_results',
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)

    # ═══════════════════════════════════════════════════════
    # TIMESTAMPS
    # ═══════════════════════════════════════════════════════
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'results'
        ordering = ['-score', '-kills', 'placement']

    def __str__(self):
        return f"{self.player_name} - {self.kills} kills"

    # ═══════════════════════════════════════════════════════
    # PROPERTIES
    # ═══════════════════════════════════════════════════════
    @property
    def is_winner(self):
        return self.prize_amount and float(self.prize_amount) > 0

    @property
    def is_top3(self):
        return 0 < self.placement <= 3

    # ═══════════════════════════════════════════════════════
    # ✅ KUBERAA POINTS CALCULATION (NAYA)
    # ═══════════════════════════════════════════════════════
    @staticmethod
    def calculate_points(entry_fee, kills):
        """
        Points calculate karo:
        - 0 kill pe: entry_fee / 5
        - 1+ kill pe: 0 points
        """
        if kills and kills > 0:
            return 0
        try:
            fee = float(entry_fee or 0)
        except (ValueError, TypeError):
            return 0
        return int(fee / 5)

    @property
    def can_earn_points(self):
        """Kya is result pe points milenge?"""
        return self.kills == 0 and self.entry_fee and float(self.entry_fee) > 0

