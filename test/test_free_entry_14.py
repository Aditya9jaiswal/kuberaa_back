# C:\Kuberaa\backend\test\test_14_referral_check.py
"""
MATCH #14 — REFERRAL CHECK (Sirf Deletion + Free Entry Check)
==============================================================
- Purana #14 delete
- Naya #14 create
- Aditya ka account ready
- Check karo: Aditya ne kisi ko refer kiya hai?
  → HAAN: FREE ENTRY DO
  → NAHI: FREE ENTRY MAT DO
- Registration NAHI karo
"""

import os
import sys
import django
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kuberaa.settings')
django.setup()

from django.utils import timezone
from apps.users.models import User
from apps.tournaments.models import Tournament, MatchRoom
from apps.matches.models import Match
from apps.results.models import Result


# ═══════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════
MY_EMAIL = 'adityajaiswal1734@gmail.com'
MY_MOBILE = '9685778431'
MY_NAME = 'Aditya'
MY_FF_NAME = 'prime_aditya'
MY_UID = '999888777'
MY_UPI = 'adityajaiswal1734@paytm'
PASSWORD = 'test1234'


# ═══════════════════════════════════════════════════════════
# STEP 1: PURANA #14 DELETE
# ═══════════════════════════════════════════════════════════
def cleanup_old():
    print("\n" + "=" * 60)
    print("STEP 1: PURANA #14 DELETE")
    print("=" * 60)

    old = Tournament.objects.filter(serial_number=14).first()
    if old:
        print(f"🗑️  Deleting: #{old.display_id} — {old.title}")
        old.delete()
        print("✅ Deleted")
    else:
        print("⏭️  #14 nahi mila")


# ═══════════════════════════════════════════════════════════
# STEP 2: NAYA #14 TOURNAMENT + ROOM
# ═══════════════════════════════════════════════════════════
def create_tournament():
    print("\n" + "=" * 60)
    print("STEP 2: NAYA #14 TOURNAMENT + ROOM")
    print("=" * 60)

    now = timezone.now()

    tournament = Tournament.objects.create(
        title='FF TEST — 14',
        description='Referral check test',
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
        notes='Test room #14',
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
# STEP 3: ADITYA KA ACCOUNT CHECK
# ═══════════════════════════════════════════════════════════
def check_aditya_account():
    print("\n" + "=" * 60)
    print("STEP 3: ADITYA KA ACCOUNT CHECK")
    print("=" * 60)

    user, created = User.objects.get_or_create(
        email=MY_EMAIL,
        defaults={
            'display_name': MY_NAME,
            'mobile_number': MY_MOBILE,
            'upi_id': MY_UPI,
            'free_fire_uid': MY_UID,
            'free_fire_name': MY_FF_NAME,
            'role': User.Role.USER,
            'status': User.Status.ACTIVE,
        },
    )

    user.display_name = MY_NAME
    user.mobile_number = MY_MOBILE
    user.upi_id = MY_UPI
    user.free_fire_uid = MY_UID
    user.free_fire_name = MY_FF_NAME
    user.set_password(PASSWORD)
    user.save()

    print(f"✅ User: {user.email}")
    print(f"   FF Name: {user.free_fire_name}")
    print(f"   Referral Code: {user.referral_code}")

    return user


# ═══════════════════════════════════════════════════════════
# STEP 4: CHECK — ADITYA NE KISI KO REFER KIYA HAI?
# ═══════════════════════════════════════════════════════════
def check_referrals(user):
    print("\n" + "=" * 60)
    print("STEP 4: CHECK — ADITYA NE KISI KO REFER KIYA HAI?")
    print("=" * 60)

    # ✅ Aditya ne kitne log refer kiye?
    referred_users = User.objects.filter(referred_by=user)
    total_referrals = referred_users.count()

    print(f"\n📊 Referral Summary:")
    print(f"   Aditya ka referral code: {user.referral_code}")
    print(f"   Total referrals: {total_referrals}")

    if total_referrals == 0:
        print("\n❌ Aditya ne kisi ko refer NAHI kiya")
        print("   → Free entry NAHI milegi")
        return {
            'has_referrals': False,
            'total_referrals': 0,
            'completed_referrals': 0,
            'referred_users': [],
            'completed_users': [],
            'pending_users': [],
        }

    # ✅ Referred users list — ✅ NAAM BHI DIKHAO
    print(f"\n👥 Referred Users ({total_referrals}):")
    for u in referred_users:
        print(f"   • {u.display_name or 'No name'} | {u.email}")
        print(f"     Referral Code: {u.referral_code}")
        print(f"     Joined: {u.date_joined.strftime('%d %b %Y, %I:%M %p')}")

    # ✅ Kitne users ne pehla match complete kiya?
    completed_users = []
    pending_users = []

    print(f"\n🔍 Checking match completion for each referred user...")
    for u in referred_users:
        completed_count = Result.objects.filter(
            user=u,
            verification_status=Result.VerificationStatus.PUBLISHED,
        ).count()

        print(f"\n   👤 {u.display_name or u.email}:")
        print(f"      Published results: {completed_count}")

        if completed_count >= 1:
            completed_users.append(u)
            print(f"      ✅ MATCH COMPLETE — Eligible for free entry")
        else:
            pending_users.append(u)
            print(f"      ❌ Match complete NAHI kiya — Not eligible")

    print(f"\n{'='*60}")
    print(f"✅ Match complete karne wale: {len(completed_users)}")
    print(f"❌ Match pending wale: {len(pending_users)}")

    if len(completed_users) == 0:
        print(f"\n❌ Kisi bhi referred user ne match complete NAHI kiya")
        print(f"   → Aditya ko FREE ENTRY NAHI milegi")
        print(f"   → Pehla match complete hone ke baad milegi")
        return {
            'has_referrals': True,
            'total_referrals': total_referrals,
            'completed_referrals': 0,
            'referred_users': list(referred_users),
            'completed_users': [],
            'pending_users': pending_users,
        }

    print(f"\n✅ {len(completed_users)} users ne match complete kiya")
    print(f"   → Aditya ko FREE ENTRY MILEGI")

    # ✅ Completed users ke naam
    print(f"\n🎉 Eligible referred users:")
    for u in completed_users:
        print(f"   • {u.display_name or u.email}")

    return {
        'has_referrals': True,
        'total_referrals': total_referrals,
        'completed_referrals': len(completed_users),
        'referred_users': list(referred_users),
        'completed_users': completed_users,
        'pending_users': pending_users,
    }


# ═══════════════════════════════════════════════════════════
# STEP 5: FREE ENTRY DO (agar referral valid hai)
# ═══════════════════════════════════════════════════════════
def maybe_give_free_entry(user, referral_info):
    print("\n" + "=" * 60)
    print("STEP 5: FREE ENTRY CHECK")
    print("=" * 60)

    if not referral_info['has_referrals']:
        print("\n⏭️  Aditya ne kisi ko refer nahi kiya")
        print("   → Free entry NAHI di jayegi")
        return False

    if referral_info['completed_referrals'] == 0:
        print("\n⏭️  Referred users ne match complete nahi kiya")
        print("   → Free entry NAHI di jayegi")
        print("   → Jab pehla match complete hoga, tab milegi")
        return False

    # ✅ Free entry do
    from apps.users.services.referral_service import ReferralService

    result = ReferralService.admin_grant_free_entry(
        user,
        amount=10,
        days=30,
    )

    print(f"\n🎁 FREE ENTRY DI GAYI!")
    print(f"   Code: {result['code']}")
    print(f"   Amount: ₹10")
    print(f"   Expires: {result['expires_at']}")

    # ✅ Verify
    user.refresh_from_db()
    has_free = ReferralService.has_free_entry_available(user)

    print(f"\n✅ Free Entry Available: {has_free}")
    print(f"   Code: {user.free_entry_code}")

    return True


# ═══════════════════════════════════════════════════════════
# STEP 6: FINAL STATUS
# ═══════════════════════════════════════════════════════════
def final_status(user, tournament, match, referral_info, free_entry_given):
    print("\n" + "=" * 60)
    print("STEP 6: FINAL STATUS")
    print("=" * 60)

    user.refresh_from_db()

    print(f"\n👤 ADITYA:")
    print(f"   Email: {user.email}")
    print(f"   FF Name: {user.free_fire_name}")
    print(f"   Referral Code: {user.referral_code}")

    # ✅ Referred users ke naam + status
    print(f"\n👥 REFERRED USERS ({referral_info['total_referrals']}):")
    if referral_info['total_referrals'] == 0:
        print(f"   ❌ Koi referral nahi")
    else:
        for u in referral_info['referred_users']:
            if u in referral_info['completed_users']:
                status = "✅ MATCH COMPLETE"
            else:
                status = "❌ MATCH PENDING"
            print(f"   • {u.display_name or u.email} — {status}")

    print(f"\n📊 REFERRAL SUMMARY:")
    print(f"   Total referrals: {referral_info['total_referrals']}")
    print(f"   Completed referrals: {referral_info['completed_referrals']}")
    print(f"   Pending referrals: {len(referral_info.get('pending_users', []))}")

    print(f"\n🎁 FREE ENTRY:")
    if free_entry_given:
        print(f"   ✅ Free entry DI GAYI")
        print(f"   Code: {user.free_entry_code}")
        print(f"   Used: {user.free_entry_used}")
        print(f"   Max Amount: ₹{user.free_entry_max_amount}")
        print(f"   Expires: {user.free_entry_expires_at}")
    else:
        print(f"   ❌ Free entry NAHI di gayi")
        print(f"   Reason: ", end="")
        if not referral_info['has_referrals']:
            print("Kisi ko refer nahi kiya")
        elif referral_info['completed_referrals'] == 0:
            print("Referred users ne match complete nahi kiya")
        else:
            print("Unknown")

    print(f"\n📱 TOURNAMENT:")
    print(f"   #{tournament.display_id} — {tournament.title}")
    print(f"   Tournament ID: {tournament.id}")
    print(f"   Match ID: {match.id}")
    print(f"   🔑 ROOM: 98765432 / abcd123")

    # ✅ FINAL VERDICT
    print(f"\n{'='*60}")
    print(f"🎯 FINAL VERDICT:")
    print(f"{'='*60}")
    if free_entry_given:
        print(f"✅ Aditya KO FREE ENTRY MILEGI")
    else:
        print(f"❌ Aditya KO FREE ENTRY NAHI MILEGI")
    print(f"{'='*60}")


# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════
def main():
    print("\n" + "█" * 60)
    print("█  MATCH #14 — REFERRAL CHECK")
    print("█" * 60)

    # 1. Purana #14 delete
    cleanup_old()

    # 2. Naya #14 create
    tournament, match = create_tournament()

    # 3. Aditya ka account ready
    user = check_aditya_account()

    # 4. Check karo — Aditya ne kisi ko refer kiya?
    referral_info = check_referrals(user)

    # 5. Free entry do (agar referral valid hai)
    free_entry_given = maybe_give_free_entry(user, referral_info)

    # 6. Final status
    final_status(user, tournament, match, referral_info, free_entry_given)

    print("\n" + "█" * 60)
    print("█  ✅ TEST COMPLETE")
    print("█" * 60)


if __name__ == '__main__':
    main()