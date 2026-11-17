# apps/users/models.py
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone
import uuid
import random
import string


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra):
        if not email:
            raise ValueError("Email required")
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault('is_staff', True)
        extra.setdefault('is_superuser', True)
        extra.setdefault('role', User.Role.SUPER_ADMIN)
        extra.setdefault('status', User.Status.ACTIVE)
        return self.create_user(email, password, **extra)


def generate_referral_code():
    """Unique referral code generate karo"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))


def generate_free_entry_code():
    """FREE-XXXXXX format ka unique code"""
    while True:
        suffix = ''.join(
            random.choices(string.ascii_uppercase + string.digits, k=6)
        )
        code = f"FREE-{suffix}"
        if not User.objects.filter(free_entry_code=code).exists():
            return code


class User(AbstractBaseUser, PermissionsMixin):
    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Active'
        INACTIVE = 'INACTIVE', 'Inactive'
        SUSPENDED = 'SUSPENDED', 'Suspended'
        BLOCKED = 'BLOCKED', 'Blocked'

    class Role(models.TextChoices):
        USER = 'USER', 'User'
        SUPER_ADMIN = 'SUPER_ADMIN', 'Super Admin'
        ADMIN = 'ADMIN', 'Admin'
        MODERATOR = 'MODERATOR', 'Moderator'
        RESULT_MANAGER = 'RESULT_MANAGER', 'Result Manager'
        SUPPORT = 'SUPPORT', 'Support'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, db_index=True)
    display_name = models.CharField(max_length=120, blank=True)
    mobile_number = models.CharField(max_length=20, blank=True, db_index=True)

    # ✅ GAME ACCOUNTS
    free_fire_uid = models.CharField(max_length=64, blank=True, db_index=True)
    free_fire_name = models.CharField(max_length=120, blank=True)
    bgmi_uid = models.CharField(max_length=64, blank=True, db_index=True)
    bgmi_name = models.CharField(max_length=120, blank=True)
    pubg_uid = models.CharField(max_length=64, blank=True, db_index=True)
    pubg_name = models.CharField(max_length=120, blank=True)
    cod_uid = models.CharField(max_length=64, blank=True, db_index=True)
    cod_name = models.CharField(max_length=120, blank=True)
    valorant_uid = models.CharField(max_length=64, blank=True, db_index=True)
    valorant_name = models.CharField(max_length=120, blank=True)

    upi_id = models.CharField(max_length=100, blank=True)
    firebase_uid = models.CharField(max_length=128, blank=True, db_index=True)
    fcm_token = models.CharField(max_length=255, blank=True, default='')

    # ✅ KUBERAA POINTS
    kuberaa_points = models.IntegerField(default=0, help_text='1 point = ₹1')
    has_played_first_match = models.BooleanField(default=False)
    first_match_free_used = models.BooleanField(default=False)

    # ✅ XP & LEVELS (NAYA)
    xp = models.IntegerField(default=0)
    level = models.IntegerField(default=1)
    badges = models.JSONField(default=list, blank=True)

    # ✅ REFERRAL
    referral_code = models.CharField(max_length=20, unique=True, blank=True, null=True, db_index=True)
    referred_by = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='referrals')
    total_referrals = models.IntegerField(default=0)
    referral_earnings = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    admin_referral_link = models.CharField(max_length=255, blank=True, null=True)
    admin_link_updated_at = models.DateTimeField(null=True, blank=True)
    admin_link_active = models.BooleanField(default=True)

    # ✅ FREE ENTRY
    free_entry_code = models.CharField(max_length=20, unique=True, blank=True, null=True, db_index=True)
    free_entry_used = models.BooleanField(default=False)
    free_entry_max_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    free_entry_expires_at = models.DateTimeField(null=True, blank=True)
    free_entry_used_at = models.DateTimeField(null=True, blank=True)
    free_entry_used_tournament = models.ForeignKey('tournaments.Tournament', on_delete=models.SET_NULL, null=True, blank=True, related_name='free_entry_users')

    wallet_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    role = models.CharField(max_length=32, choices=Role.choices, default=Role.USER)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        db_table = 'users'

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        if not self.referral_code:
            code = generate_referral_code()
            while User.objects.filter(referral_code=code).exists():
                code = generate_referral_code()
            self.referral_code = code
        super().save(*args, **kwargs)

    @property
    def is_admin_role(self):
        return self.role in {self.Role.SUPER_ADMIN, self.Role.ADMIN, self.Role.MODERATOR, self.Role.RESULT_MANAGER, self.Role.SUPPORT}

    @property
    def is_super_admin(self):
        return self.role == self.Role.SUPER_ADMIN

    @property
    def has_free_entry_available(self):
        if not self.free_entry_code: return False
        if self.free_entry_used: return False
        if self.free_entry_expires_at and self.free_entry_expires_at < timezone.now(): return False
        return True

    @property
    def is_new_user(self):
        return not self.has_played_first_match

    @property
    def can_use_first_free(self):
        return not self.has_played_first_match and not self.first_match_free_used

    @property
    def can_use_points(self):
        return self.kuberaa_points > 0

    def add_points(self, points):
        if points <= 0: return
        self.kuberaa_points = (self.kuberaa_points or 0) + points
        self.save(update_fields=['kuberaa_points'])

    def deduct_points(self, points):
        if points <= 0: return False
        if self.kuberaa_points < points: return False
        self.kuberaa_points = self.kuberaa_points - points
        self.save(update_fields=['kuberaa_points'])
        return True

    def add_xp(self, amount):
        """Match publish hone pe XP add karo"""
        if amount <= 0: return
        self.xp += amount
        self.level = (self.xp // 500) + 1
        self.save(update_fields=['xp', 'level'])

    def get_game_uid(self, game_type):
        game_map = {'FREEFIRE': self.free_fire_uid, 'BGMI': self.bgmi_uid, 'PUBG': self.pubg_uid, 'COD': self.cod_uid, 'VALORANT': self.valorant_uid}
        return game_map.get(game_type.upper(), '')

    def get_game_name(self, game_type):
        game_map = {'FREEFIRE': self.free_fire_name, 'BGMI': self.bgmi_name, 'PUBG': self.pubg_name, 'COD': self.cod_name, 'VALORANT': self.valorant_name}
        return game_map.get(game_type.upper(), '')

    def set_game_account(self, game_type, uid, name):
        game = game_type.upper()
        if game == 'FREEFIRE': self.free_fire_uid, self.free_fire_name = uid, name
        elif game == 'BGMI': self.bgmi_uid, self.bgmi_name = uid, name
        elif game == 'PUBG': self.pubg_uid, self.pubg_name = uid, name
        elif game == 'COD': self.cod_uid, self.cod_name = uid, name
        elif game == 'VALORANT': self.valorant_uid, self.valorant_name = uid, name
        self.save()

    @property
    def has_any_game_account(self):
        return any([self.free_fire_uid, self.bgmi_uid, self.pubg_uid, self.cod_uid, self.valorant_uid])


class PasswordResetOTP(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='otps')
    otp_hash = models.CharField(max_length=128)
    attempts = models.PositiveIntegerField(default=0)
    max_attempts = models.PositiveIntegerField(default=5)
    is_used = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'password_reset_otps'
        ordering = ['-created_at']

    def is_expired(self):
        return timezone.now() >= self.expires_at

    def is_valid(self):
        return not self.is_used and not self.is_expired() and self.attempts < self.max_attempts

# apps/users/models.py (Sabse neeche add karo)

class GlobalReferralLink(models.Model):
    """
    Admin ek hi global link set karega. Sabhi users yahi link share karenge.
    """
    download_link = models.URLField(
        max_length=500, 
        default="https://kuberaa.app/download",
        help_text="Play Store ya APK ka link"
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.download_link

    @classmethod
    def get_link(cls):
        # Hamesha pehla (aur ekmatra) record return karega
        obj, created = cls.objects.get_or_create(id=1)
        return obj.download_link