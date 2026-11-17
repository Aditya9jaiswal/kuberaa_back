# C:\Kuberaa\backend\test\test_payment_flow.py
"""
PAYMENT → RESULT → WINNING FLOW TEST — Aditya Account
Ek-ek step me chalega, Enter press karke next step
"""

import os
import django
import time

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kuberaa.settings')
django.setup()

from django.utils import timezone
from apps.users.models import User
from apps.tournaments.models import Tournament, Registration
from apps.payments.models import PaymentScreenshot
from apps.notifications.services import NotificationService


# ═══════════════════════════════════════════════════════════
# TUMPARA ACCOUNT
# ═══════════════════════════════════════════════════════════
MY_EMAIL = 'adityajaiswal1734@gmail.com'
MY_MOBILE = '9685778431'
MY_NAME = 'Aditya'
MY_UID = '999888777'
MY_UPI = 'adityajaiswal1734@paytm'


def wait_for_enter(step_name):
    """User ke Enter press karne ka wait karo"""
    print("\n" + "─" * 60)
    input(f"⏸  [{step_name}] — Phone pe check karo, phir Enter dabao...")
    print("─" * 60)


# ═══════════════════════════════════════════════════════════
# STEP 1: PAYMENT UPLOAD (user side)
# ═══════════════════════════════════════════════════════════
def step1_payment_upload():
    print("\n" + "=" * 60)
    print("STEP 1: 💰 PAYMENT UPLOAD (user ne screenshot daala)")
    print("=" * 60)

    user = User.objects.get(email=MY_EMAIL)
    print(f"👤 User: {user.email}")
    print(f"📛 Name: {user.display_name}")
    print(f"📱 FCM Token: {'✅ YES' if user.fcm_token else '❌ NO — notification nahi aayega!'}")

    # Latest tournament
    tournament = Tournament.objects.order_by('-serial_number').first()
    if not tournament:
        print("❌ Koi tournament nahi hai")
        return None, None, None

    print(f"\n🏆 Tournament: #{tournament.display_id} — {tournament.title}")
    print(f"💵 Entry Fee: ₹{tournament.entry_fee}")

    # Registration
    reg = Registration.objects.filter(
        tournament=tournament,
        user=user,
    ).first()

    if not reg:
        print("❌ Registration not found — pehle register karo")
        return None, None, None

    print(f"📝 Registration ID: {reg.id}")
    print(f"📊 Status: {reg.status}")
    print(f"🎮 Can Play: {reg.can_play}")

    # Payment record
    payment, created = PaymentScreenshot.objects.get_or_create(
        uploaded_by=user,
        tournament_id=tournament.id,
        defaults={
            'amount': tournament.entry_fee,
            'transaction_id': '123456789012',
            'payment_app': 'PhonePe',
            'status': 'pending',
        },
    )

    if not created:
        payment.status = 'pending'
        payment.transaction_id = '123456789012'
        payment.save()

    # Registration status
    reg.status = Registration.Status.PAYMENT_SUBMITTED
    reg.save()

    print(f"\n✅ Payment uploaded")
    print(f"   Status: {payment.status}")
    print(f"   UTR: {payment.transaction_id}")
    print(f"   Amount: ₹{payment.amount}")

    # ⚠️ NOTE: Payment upload hone pe notification NAHI jaata
    # Admin verify karega tab jaayega
    print(f"\n⏳ Ab admin verify karega...")

    return user, payment, reg


# ═══════════════════════════════════════════════════════════
# STEP 2: ADMIN APPROVE → PAYMENT VERIFIED NOTIFICATION
# ═══════════════════════════════════════════════════════════
def step2_admin_approve(user, payment, reg):
    print("\n" + "=" * 60)
    print("STEP 2: ✅ ADMIN APPROVE (payment verified)")
    print("=" * 60)

    # Admin approve
    payment.status = 'verified'
    payment.verified_at = timezone.now()
    payment.save()

    reg.status = Registration.Status.CONFIRMED
    reg.can_play = True
    reg.save()

    print(f"✅ Payment approved")
    print(f"   Payment status: {payment.status}")
    print(f"   Registration status: {reg.status}")
    print(f"   Can Play: {reg.can_play}")

    # 🔔 NOTIFICATION
    print(f"\n🔔 SENDING PAYMENT VERIFIED NOTIFICATION...")

    try:
        result = NotificationService.send_payment_verified(
            user=reg.user,
            tournament=reg.tournament,
        )

        print(f"✅ Notification sent!")
        print(f"   ID: {result.id}")
        print(f"   Title: {result.title}")
        print(f"   Body: {result.body}")
        print(f"   Type: {result.notification_type}")

        print(f"\n📱 PHONE PE CHECK KARO:")
        print(f"   🔊 Sound: payment.mp3")
        print(f"   📳 Vibration")
        print(f"   💬 '{result.title}'")

    except Exception as e:
        print(f"❌ Notification failed: {e}")
        import traceback
        traceback.print_exc()

    return payment, reg


# ═══════════════════════════════════════════════════════════
# STEP 3: ROOM RELEASED (optional — 5 min pehle)
# ═══════════════════════════════════════════════════════════
def step3_room_released(user, tournament):
    print("\n" + "=" * 60)
    print("STEP 3: 🚪 ROOM RELEASED (5 min pehle)")
    print("=" * 60)

    try:
        result = NotificationService.send_room_released(
            user=user,
            tournament=tournament,
            room_id='98765432',
        )
        print(f"✅ Notification sent!")
        print(f"   Title: {result.title}")
        print(f"   Body: {result.body}")
        print(f"\n📱 PHONE PE CHECK KARO:")
        print(f"   🔊 Sound: room.mp3")
    except Exception as e:
        print(f"❌ Notification failed: {e}")


# ═══════════════════════════════════════════════════════════
# STEP 4: RESULT PUBLISHED
# ═══════════════════════════════════════════════════════════
def step4_result_published(user, tournament):
    print("\n" + "=" * 60)
    print("STEP 4: 📤 RESULT PUBLISHED")
    print("=" * 60)

    try:
        result = NotificationService.send_result_published(
            user=user,
            tournament=tournament,
        )
        print(f"✅ Notification sent!")
        print(f"   Title: {result.title}")
        print(f"   Body: {result.body}")
        print(f"\n📱 PHONE PE CHECK KARO:")
        print(f"   🔊 Sound: result.mp3")
    except Exception as e:
        print(f"❌ Notification failed: {e}")


# ═══════════════════════════════════════════════════════════
# STEP 5: WINNING
# ═══════════════════════════════════════════════════════════
def step5_winning(user, tournament):
    print("\n" + "=" * 60)
    print("STEP 5: 🏆 WINNING (prize jeeta)")
    print("=" * 60)

    try:
        result = NotificationService.send_winning(
            user=user,
            tournament=tournament,
            prize_amount=75.0,
            kills=10,
            placement=1,
        )
        print(f"✅ Notification sent!")
        print(f"   Title: {result.title}")
        print(f"   Body: {result.body}")
        print(f"\n📱 PHONE PE CHECK KARO:")
        print(f"   🔊 Sound: winning.mp3")
        print(f"   📳 Triple vibration")
    except Exception as e:
        print(f"❌ Notification failed: {e}")


# ═══════════════════════════════════════════════════════════
# MAIN — Ek-ek step, Enter press karke
# ═══════════════════════════════════════════════════════════
def main():
    print("\n" + "█" * 60)
    print("█  💰 PAYMENT → RESULT → WINNING FLOW TEST")
    print("█" * 60)
    print(f"\n🌟 ACCOUNT: {MY_EMAIL}")
    print(f"📱 Har step ke baad phone pe check karo")
    print(f"⌨️  Enter press karke next step pe jao")

    # ═══════════════════════════════════════════════════════
    # STEP 1: PAYMENT UPLOAD
    # ═══════════════════════════════════════════════════════
    user, payment, reg = step1_payment_upload()
    if not payment or not reg:
        return

    wait_for_enter("STEP 1 DONE — Phone pe dekho (notification nahi aayega)")

    # ═══════════════════════════════════════════════════════
    # STEP 2: ADMIN APPROVE → PAYMENT VERIFIED
    # ═══════════════════════════════════════════════════════
    payment, reg = step2_admin_approve(user, payment, reg)

    wait_for_enter("STEP 2 DONE — payment.mp3 bajna chahiye")

    # ═══════════════════════════════════════════════════════
    # STEP 3: ROOM RELEASED (optional)
    # ═══════════════════════════════════════════════════════
    tournament = reg.tournament
    step3_room_released(user, tournament)

    wait_for_enter("STEP 3 DONE — room.mp3 bajna chahiye")

    # ═══════════════════════════════════════════════════════
    # STEP 4: RESULT PUBLISHED
    # ═══════════════════════════════════════════════════════
    step4_result_published(user, tournament)

    wait_for_enter("STEP 4 DONE — result.mp3 bajna chahiye")

    # ═══════════════════════════════════════════════════════
    # STEP 5: WINNING
    # ═══════════════════════════════════════════════════════
    step5_winning(user, tournament)

    wait_for_enter("STEP 5 DONE — winning.mp3 bajna chahiye")

    # ═══════════════════════════════════════════════════════
    # DONE
    # ═══════════════════════════════════════════════════════
    print("\n" + "█" * 60)
    print("█  ✅ ALL STEPS COMPLETE")
    print("█" * 60)
    print("\n📋 SUMMARY:")
    print("   1. Payment upload       — koi sound nahi (sahi hai)")
    print("   2. Payment verified     — payment.mp3 ✅")
    print("   3. Room released        — room.mp3 ✅")
    print("   4. Result published     — result.mp3 ✅")
    print("   5. Winning              — winning.mp3 ✅")


if __name__ == '__main__':
    main()