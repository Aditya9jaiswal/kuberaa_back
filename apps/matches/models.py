from django.db import models
from django.utils import timezone
import uuid


class Match(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = 'SCHEDULED', 'Scheduled'
        ROOM_RELEASED = 'ROOM_RELEASED', 'Room Released'
        LIVE = 'LIVE', 'Live'
        COMPLETED = 'COMPLETED', 'Completed'
        CANCELLED = 'CANCELLED', 'Cancelled'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    tournament = models.ForeignKey(
        'tournaments.Tournament',
        on_delete=models.CASCADE,
        related_name='matches',
    )

    match_number = models.PositiveIntegerField()

    # Match ka naam (optional, default "Match X")
    title = models.CharField(max_length=200, blank=True)

    scheduled_start_time = models.DateTimeField()

    room_release_time = models.DateTimeField(
        help_text='Room credentials become visible at this time (5 min before start)'
    )

    # Room credentials — HIDDEN until room_release_time
    room_id = models.CharField(max_length=64, blank=True)
    room_password = models.CharField(max_length=64, blank=True)

    # Admin notes
    room_notes = models.TextField(blank=True)

    # Match config
    max_participants = models.PositiveIntegerField(default=50)
    entry_fee = models.DecimalField(
        max_digits=10, decimal_places=2, default=0
    )

    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.SCHEDULED,
        db_index=True,
    )

    created_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_matches',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'matches'
        unique_together = [('tournament', 'match_number')]
        ordering = ['scheduled_start_time']

    def __str__(self):
        return f"Match {self.match_number} - #{self.tournament.display_id}"

    @property
    def display_name(self):
        return self.title or f"Match {self.match_number}"

    @property
    def is_room_available(self):
        """Room visible only when current time >= release time"""
        return timezone.now() >= self.room_release_time

    @property
    def minutes_until_release(self):
        """Minutes until room release (0 if released)"""
        if self.is_room_available:
            return 0
        diff = self.room_release_time - timezone.now()
        return max(0, int(diff.total_seconds() / 60))

    @property
    def minutes_until_start(self):
        """Minutes until match start (0 if started)"""
        now = timezone.now()
        if now >= self.scheduled_start_time:
            return 0
        diff = self.scheduled_start_time - now
        return max(0, int(diff.total_seconds() / 60))


class MatchParticipant(models.Model):
    """
    Users approved for this match.
    Admin verifies each user — sees payment info.
    Room access ONLY for APPROVED users.
    """

    class Status(models.TextChoices):
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'
        PENDING = 'PENDING', 'Pending'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    match = models.ForeignKey(
        Match,
        on_delete=models.CASCADE,
        related_name='participants',
    )

    user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='match_participations',
    )

    # Link to registration (for payment screenshot access)
    registration = models.ForeignKey(
        'tournaments.Registration',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='match_participations',
    )

    # Snapshot of user info
    user_email = models.CharField(max_length=254, blank=True)
    user_mobile = models.CharField(max_length=20, blank=True)
    user_ff_uid = models.CharField(max_length=64, blank=True, db_index=True)
    user_ff_name = models.CharField(max_length=120, blank=True)
    user_upi_id = models.CharField(max_length=100, blank=True)

    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )

    # Room access granted?
    room_access_granted = models.BooleanField(default=False)

    approved_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='approved_participants',
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'match_participants'
        unique_together = [('match', 'user')]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user_email} → Match {self.match.match_number}"