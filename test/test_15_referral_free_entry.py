# C:\Kuberaa\backend\test\test_16_referral_full_flow.py
"""
MATCH #16 — REFERRAL FULL FLOW TEST
=====================================
Real flow jaise app mein hota hai:

STEP 1: Purana #16 delete
STEP 2: Naya #16 tournament + match create
STEP 3: Aditya ka account ready (referrer)
STEP 4: Naya user banao (referred by Aditya)
STEP 5: Naya user tournament mein REGISTER kare
STEP 6: Naya user PAYMENT kare
STEP 7: Naya user MATCH KHELE (result published)
STEP 8: Check karo — Aditya free entry eligible hai?
STEP 9: Aditya ko FREE ENTRY do
STEP 10: Final status
"""

import os
import sys
import django
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kuberaa.settings')
django.setup()

from django.utils import timezone
from django.db import transaction
from apps.users.models import User
from apps.tournaments.models import Tournament, MatchRoom, Registration
from apps.matches.models import Match
from apps.results.models import Result


# ═══════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════
ADITYA_EMAIL = 'adityajaiswal1734@gmail.com'
ADITYA_MOBILE = '9685778431'
ADITYA_NAME = 'Aditya'
ADITYA_FF_NAME = 'prime_aditya'
ADITYA_UID = '999888777'
ADITYA_UPI = 'adityajaiswal1734@paytm'

NEW_EMAIL = 'new_player_referral@example.com'
NEW_MOBILE = '9876543210'
NEW_NAME = 'New Referred Player'
NEW_FF_NAME = 'new_referred_ff'
NEW_UID = '111222333'
NEW_UPI = 'newplayer@paytm'

PASSWORD = 'test1234'


# ═══════════════════════════════════════════════════════════
# STEP 1: PURANA #16 DELETE
# ═══════════════════════════════════════════════════════════
def cleanup_old():
    print("\n" + "=" * 60)
    print("STEP 1: PURANA #16 DELETE")
    print("=" * 60)

    old = Tournament.objects.filter(serial_number=16).first()
    if old:
        print(f"🗑️  Deleting: #{old.display_id} — {old.title}")
        old.delete()
        print("✅ Deleted")
    else:
        print("⏭️  #16 nahi mila")


# ═══════════════════════════════════════════════════════════
# STEP 2: NAYA #16 TOURNAMENT + MATCH
# ═══════════════════════════════════════════════════════════
def create_tournament():
    print("\n" + "=" * 60)
    print("STEP 2: NAYA #16 TOURNAMENT + MATCH")
    print("=" * 60)

    now = timezone.now()

    tournament = Tournament.objects.create(
        title='FF TEST — 16',
        description='Referral full flow test',
        rules='Fair play',
        prize_info='₹500',
        tournament_type='FREEFIRE',
        tournament_date=now.date(),
        start_time=now + timedelta(minutes=30),
        registration_start=now - timedelta(hours=1),
        registration_end=now + timedelta(minutes=20),
        maximum_participants=48,
        entry_fee=10,
        upi_id='admin@paytm',
        upi_name='Kuberaa Admin',
        status=Tournament.Status.OPEN,
    )

    room = MatchRoom.objects.create(
        tournament=tournament,
        room_id='98765432',
        room_password='abcd123',
        scheduled_at=now + timedelta(minutes=30),
        notes='Test room #16',
    )

    match = Match.objects.create(
        tournament=tournament,
        match_number=1,
        title=f'{tournament.title} — Match 1',
        scheduled_start_time=now + timedelta(minutes=30),
        room_release_time=now + timedelta(minutes=25),
        room_id='98765432',
        room_password='abcd123',
        max_participants=48,
        entry_fee=tournament.entry_fee,
        status=Match.Status.SCHEDULED,
    )

    print(f"✅ Tournament: #{tournament.display_id} — {tournament.title}")
    print(f"   Tournament ID: {tournament.id}")
    print(f"   Entry Fee: ₹{tournament.entry_fee}")
    print(f"   🔑 ROOM: {room.room_id} / {room.room_password}")
    print(f"✅ Match ID: {match.id}")

    return tournament, match


# ═══════════════════════════════════════════════════════════
# STEP 3: ADITYA KA ACCOUNT READY (REFERRER)
# ═══════════════════════════════════════════════════════════
def setup_aditya():
    print("\n" + "=" * 60)
    print("STEP 3: ADITYA KA ACCOUNT READY (REFERRER)")
    print("=" * 60)

    user, created = User.objects.get_or_create(
        email=ADITYA_EMAIL,
        defaults={
            'display_name': ADITYA_NAME,
            'mobile_number': ADITYA_MOBILE,
            'upi_id': ADITYA_UPI,
            'free_fire_uid': ADITYA_UID,
            'free_fire_name': ADITYA_FF_NAME,
            'role': User.Role.USER,
            'status': User.Status.ACTIVE,
        },
    )

    user.display_name = ADITYA_NAME
    user.mobile_number = ADITYA_MOBILE
    user.upi_id = ADITYA_UPI
    user.free_fire_uid = ADITYA_UID
    user.free_fire_name = ADITYA_FF_NAME
    user.set_password(PASSWORD)

    # ✅ Free entry reset
    user.free_entry_code = None
    user.free_entry_used = False
    user.free_entry_max_amount = 0
    user.free_entry_expires_at = None
    user.free_entry_used_at = None
    user.free_entry_used_tournament = None

    user.save()

    print(f"✅ Aditya (Referrer):")
    print(f"   Email: {user.email}")
    print(f"   FF Name: {user.free_fire_name}")
    print(f"   Referral Code: {user.referral_code}")

    return user


# ═══════════════════════════════════════════════════════════
# STEP 4: NAYA USER BANAO (REFERRED BY ADITYA)
# ═══════════════════════════════════════════════════════════
def create_new_user(aditya):
    print("\n" + "=" * 60)
    print("STEP 4: NAYA USER BANAO (REFERRED BY ADITYA)")
    print("=" * 60)

    # ✅ Purana user delete karo (agar hai)
    old = User.objects.filter(email=NEW_EMAIL).first()
    if old:
        print(f"🗑️  Purana user delete: {old.email}")
        old.delete()

    # ✅ Naya user banao — Aditya ne refer kiya
    new_user = User.objects.create(
        email=NEW_EMAIL,
        display_name=NEW_NAME,
        mobile_number=NEW_MOBILE,
        upi_id=NEW_UPI,
        free_fire_uid=NEW_UID,
        free_fire_name=NEW_FF_NAME,
        referred_by=aditya,  # ✅ Aditya ne refer kiya
        role=User.Role.USER,
        status=User.Status.ACTIVE,
    )
    new_user.set_password(PASSWORD)
    new_user.save()

    print(f"✅ Naya User Created:")
    print(f"   Email: {new_user.email}")
    print(f"   Name: {new_user.display_name}")
    print(f"   FF Name: {new_user.free_fire_name}")
    print(f"   Referred by: {aditya.display_name} ({aditya.referral_code})")

    return new_user


# ═══════════════════════════════════════════════════════════
# STEP 5: NAYA USER TOURNAMENT MEIN REGISTER KARE
# ═══════════════════════════════════════════════════════════
def register_tournament(new_user, tournament):
    print("\n" + "=" * 60)
    print("STEP 5: NAYA USER TOURNAMENT MEIN REGISTER KARE")
    print("=" * 60)

    # ✅ Purana registration delete karo (agar hai)
    old = Registration.objects.filter(
        user=new_user,
        tournament=tournament,
    ).first()
    if old:
        print(f"🗑️  Purana registration delete: {old.id}")
        old.delete()

    # ✅ Naya registration banao
    registration = Registration.objects.create(
        user=new_user,
        tournament=tournament,
        free_fire_uid=NEW_UID,
        free_fire_name=NEW_FF_NAME,
        user_upi_id=NEW_UPI,
        user_mobile=NEW_MOBILE,
        status=Registration.Status.PENDING_PAYMENT,
    )

    print(f"✅ Registration Created:")
    print(f"   Registration ID: {registration.id}")
    print(f"   User: {new_user.display_name}")
    print(f"   Tournament: {tournament.title}")
    print(f"   Status: {registration.status}")

    return registration


# ═══════════════════════════════════════════════════════════
# STEP 6: NAYA USER PAYMENT KARE
# ═══════════════════════════════════════════════════════════
def make_payment(registration, tournament):
    print("\n" + "=" * 60)
    print("STEP 6: NAYA USER PAYMENT KARE")
    print("=" * 60)

    # ✅ Payment details update karo
    registration.utr_number = 'TEST1234567890'
    registration.payment_amount = tournament.entry_fee
    registration.payment_app = 'PhonePe'
    registration.status = Registration.Status.PAYMENT_SUBMITTED
    registration.save()

    print(f"✅ Payment Submitted:")
    print(f"   UTR: {registration.utr_number}")
    print(f"   Amount: ₹{registration.payment_amount}")
    print(f"   App: {registration.payment_app}")
    print(f"   Status: {registration.status}")

    # ✅ Admin approve karo
    registration.status = Registration.Status.CONFIRMED
    registration.save()

    print(f"\n✅ Admin ne payment approve kiya")
    print(f"   Status: {registration.status}")

    return registration


# ═══════════════════════════════════════════════════════════
# STEP 7: NAYA USER MATCH KHELE
# ═══════════════════════════════════════════════════════════
def play_match(new_user, match):
    print("\n" + "=" * 60)
    print("STEP 7: NAYA USER MATCH KHELE")
    print("=" * 60)

    # ✅ Purana result delete karo (agar hai)
    old = Result.objects.filter(user=new_user, match=match).first()
    if old:
        print(f"🗑️  Purana result delete: {old.id}")
        old.delete()

    # ✅ Naya result banao — PUBLISHED
    result = Result.objects.create(
        user=new_user,
        match=match,
        placement=1,
        kills=7,
        prize_amount=200,
        verification_status=Result.VerificationStatus.PUBLISHED,
    )

    print(f"✅ Match Result Created:")
    print(f"   Player: {new_user.display_name}")
    print(f"   Match: {match.title}")
    print(f"   Placement: #{result.placement}")
    print(f"   Kills: {result.kills}")
    print(f"   Prize: ₹{result.prize_amount}")
    print(f"   Status: {result.verification_status}")

    return result


# ═══════════════════════════════════════════════════════════
# STEP 8: CHECK — ADITYA FREE ENTRY ELIGIBLE HAI?
# ═══════════════════════════════════════════════════════════
def check_free_entry_eligibility(aditya):
    print("\n" + "=" * 60)
    print("STEP 8: CHECK — ADITYA FREE ENTRY ELIGIBLE HAI?")
    print("=" * 60)

    referred_users = User.objects.filter(referred_by=aditya)
    total_referrals = referred_users.count()

    print(f"\n📊 Referral Summary:")
    print(f"   Aditya ka referral code: {aditya.referral_code}")
    print(f"   Total referrals: {total_referrals}")

    if total_referrals == 0:
        print(f"\n❌ Aditya ne kisi ko refer NAHI kiya")
        return {
            'eligible': False,
            'has_referrals': False,
            'total_referrals': 0,
            'completed_referrals': 0,
            'reason': 'Kisi ko refer nahi kiya',
        }

    # ✅ Referred users list
    print(f"\n👥 Referred Users ({total_referrals}):")
    for u in referred_users:
        print(f"   • {u.display_name or u.email} | {u.email}")

    # ✅ Check karo kitne ne match complete kiya
    completed_users = []
    pending_users = []

    print(f"\n🔍 Match completion check:")
    for u in referred_users:
        completed_count = Result.objects.filter(
            user=u,
            verification_status=Result.VerificationStatus.PUBLISHED,
        ).count()

        print(f"\n   👤 {u.display_name or u.email}:")
        print(f"      Published results: {completed_count}")

        if completed_count >= 1:
            completed_users.append(u)
            print(f"      ✅ MATCH COMPLETE")
        else:
            pending_users.append(u)
            print(f"      ❌ MATCH PENDING")

    if len(completed_users) == 0:
        print(f"\n❌ Kisi bhi referred user ne match complete NAHI kiya")
        return {
            'eligible': False,
            'has_referrals': True,
            'total_referrals': total_referrals,
            'completed_referrals': 0,
            'completed_users': [],
            'pending_users': pending_users,
            'reason': 'Referred users ne match complete nahi kiya',
        }

    print(f"\n✅ {len(completed_users)} users ne match complete kiya")
    print(f"   → Aditya FREE ENTRY ke liye eligible hai")

    return {
        'eligible': True,
        'has_referrals': True,
        'total_referrals': total_referrals,
        'completed_referrals': len(completed_users),
        'completed_users': completed_users,
        'pending_users': pending_users,
        'reason': 'Eligible',
    }


# ═══════════════════════════════════════════════════════════
# STEP 9: ADITYA KO FREE ENTRY DO
# ═══════════════════════════════════════════════════════════
def give_free_entry(aditya, eligibility):
    print("\n" + "=" * 60)
    print("STEP 9: ADITYA KO FREE ENTRY DO")
    print("=" * 60)

    if not eligibility['eligible']:
        print(f"\n❌ Aditya free entry ke liye eligible NAHI hai")
        print(f"   Reason: {eligibility['reason']}")
        return False

    from apps.users.services.referral_service import ReferralService

    result = ReferralService.admin_grant_free_entry(
        aditya,
        amount=10,
        days=30,
    )

    print(f"\n🎁 FREE ENTRY DI GAYI!")
    print(f"   Code: {result['code']}")
    print(f"   Amount: ₹10")
    print(f"   Expires: {result['expires_at']}")

    aditya.refresh_from_db()
    has_free = ReferralService.has_free_entry_available(aditya)

    print(f"\n✅ Free Entry Available: {has_free}")
    print(f"   Code: {aditya.free_entry_code}")
    print(f"   Max Amount: ₹{aditya.free_entry_max_amount}")

    return True


# ═══════════════════════════════════════════════════════════
# STEP 10: FINAL STATUS
# ═══════════════════════════════════════════════════════════
def final_status(aditya, new_user, tournament, match, registration, eligibility, free_entry_given):
    print("\n" + "=" * 60)
    print("STEP 10: FINAL STATUS")
    print("=" * 60)

    aditya.refresh_from_db()

    print(f"\n👤 ADITYA (Referrer):")
    print(f"   Email: {aditya.email}")
    print(f"   FF Name: {aditya.free_fire_name}")
    print(f"   Referral Code: {aditya.referral_code}")

    print(f"\n👤 NEW PLAYER (Referred):")
    print(f"   Email: {new_user.email}")
    print(f"   Name: {new_user.display_name}")
    print(f"   FF Name: {new_user.free_fire_name}")
    print(f"   Referred by: {aditya.display_name}")

    print(f"\n📋 REGISTRATION:")
    print(f"   ID: {registration.id}")
    print(f"   Status: {registration.status}")
    print(f"   UTR: {registration.utr_number}")
    print(f"   Amount: ₹{registration.payment_amount}")

    print(f"\n📊 REFERRAL SUMMARY:")
    print(f"   Total referrals: {eligibility.get('total_referrals', 0)}")
    print(f"   Completed referrals: {eligibility.get('completed_referrals', 0)}")
    print(f"   Pending referrals: {len(eligibility.get('pending_users', []))}")

    print(f"\n🎁 FREE ENTRY:")
    if free_entry_given:
        print(f"   ✅ Free entry DI GAYI")
        print(f"   Code: {aditya.free_entry_code}")
        print(f"   Max Amount: ₹{aditya.free_entry_max_amount}")
        print(f"   Expires: {aditya.free_entry_expires_at}")
    else:
        print(f"   ❌ Free entry NAHI di gayi")
        print(f"   Reason: {eligibility.get('reason', 'Unknown')}")

    print(f"\n📱 TOURNAMENT:")
    print(f"   #{tournament.display_id} — {tournament.title}")
    print(f"   Tournament ID: {tournament.id}")
    print(f"   Match ID: {match.id}")
    print(f"   🔑 ROOM: {match.room_id} / {match.room_password}")

    # ✅ FINAL VERDICT
    print(f"\n{'='*60}")
    print(f"🎯 FINAL VERDICT")
    print(f"{'='*60}")
    if free_entry_given:
        print(f"✅ Aditya KO FREE ENTRY MILI")
        print(f"   Reason: Uske referred player ne match complete kiya")
    else:
        print(f"❌ Aditya KO FREE ENTRY NAHI MILI")
        print(f"   Reason: {eligibility.get('reason', 'Unknown')}")
    print(f"{'='*60}")


# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════
def main():
    print("\n" + "█" * 60)
    print("█  MATCH #16 — REFERRAL FULL FLOW TEST")
    print("█  (Registration + Payment + Match + Result)")
    print("█" * 60)

    # 1. Purana #16 delete
    cleanup_old()

    # 2. Naya #16 create
    tournament, match = create_tournament()

    # 3. Aditya ready
    aditya = setup_aditya()

    # 4. Naya user banao (Aditya ne refer kiya)
    new_user = create_new_user(aditya)

    # 5. Naya user register kare
    registration = register_tournament(new_user, tournament)

    # 6. Naya user payment kare
    registration = make_payment(registration, tournament)

    # 7. Naya user match khele
    play_match(new_user, match)

    # 8. Check — Aditya eligible hai?
    eligibility = check_free_entry_eligibility(aditya)

    # 9. Free entry do
    free_entry_given = give_free_entry(aditya, eligibility)

    # 10. Final status
    final_status(
        aditya, new_user, tournament, match,
        registration, eligibility, free_entry_given
    )

    print("\n" + "█" * 60)
    print("█  ✅ TEST COMPLETE")
    print("█" * 60)


if __name__ == '__main__':
    main()