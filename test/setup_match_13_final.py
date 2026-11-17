# C:\Kuberaa\backend\test\setup_match_13_final.py
"""
FINAL SETUP — Match #13 + Aditya Winner + 32 Players
=====================================================
- Purana #13 delete
- Naya #13 + Room + Match
- 32 players register (fake UID, UPI, Mobile)
- ✅ Aditya already WINNER (5 kills, Rank #1)
- Baaki players ka result screenshot OCR se aayega
- Future mein real data ke saath bhi kaam karega
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
from apps.tournaments.models import Tournament, Registration, MatchRoom
from apps.matches.models import Match
from apps.results.models import Result
from apps.results.utils.prize_calculator import (
    calculate_per_kill_prize,
    calculate_prize_amount,
    calculate_score,
)


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

# ✅ Aditya ka result (already winner)
MY_KILLS = 5
MY_RANK = 1


# ═══════════════════════════════════════════════════════════
# ✅ 32 PLAYERS FROM SCREENSHOT
# (Name, Kills, Rank)
# ═══════════════════════════════════════════════════════════
SCREENSHOT_PLAYERS = [
    # Rank 1
    ('_RANCHI_', 0, 1),
    ('LAUT !!', 4, 1),
    ('ꜱɴᴏᴡRider', 1, 1),
    ('prime_aditya', 4, 1),      # 🌟 AAP (5 kills manual override hoga)
    
    # Rank 2
    ('DGZpintu83', 3, 2),
    ('Kay9V6!', 4, 2),
    ('DGZ Op.Max07', 13, 2),
    ('@Ayan@07m', 1, 2),
    
    # Rank 3
    ('SANCHIT᭄亗™', 1, 3),
    ('Dequan60035K', 0, 3),
    ('MIVA_BHAI,⁷⁸⁶', 1, 3),
    ('XRAJPUTKINGX', 2, 3),
    
    # Rank 4
    ('Ivy0F4B0', 0, 4),
    ('IQOO.TG5AKXY', 7, 4),
    ('Aqua9s0X9U', 1, 4),
    ('ꜱʜᴀʀᴜᴋʜ*44ꜱ', 0, 4),
    
    # Rank 5
    ('GK_JSM_⊱♛7', 5, 5),
    ('ꜱᴀᴋʜɪʟ-ꜰꜰ ツ', 2, 5),
    ('ꜱʟᴜᴄɪꜰᴇʀッ', 3, 5),
    ('@TP_white444', 1, 5),
    
    # Rank 6
    ('AURA-STROMY', 1, 6),
    ('Zayon ✿', 0, 6),
    ('Hacrry', 5, 6),
    ('ᴛᴇᴀᴍ♪ᴛꜱ7123', 0, 6),
    
    # Rank 7
    ('ꜱᴏɴᴀ', 1, 7),
    ('乃ᴀᴅʜᴀɴシ', 0, 7),
    ('イㅓKᴀRᴀɴ', 0, 7),
    ('ᴛ ᴛYᴀ', 0, 7),
    
    # Rank 8
    ('ONLY- zxu-', 0, 8),
    ('PIRNSPRO™', 1, 8),
    ('tamjannamaj', 0, 8),
    ('abhaygamerz2', 0, 8),
]


# ═══════════════════════════════════════════════════════════
# FAKE DATA GENERATORS
# ═══════════════════════════════════════════════════════════
def fake_uid(i):
    """Unique 9-digit Free Fire UID."""
    return str(200000000 + i)


def fake_mobile(i):
    """Unique 10-digit mobile — India style."""
    # 7000000001, 7000000002... (valid Indian mobile range)
    return str(7000000001 + i)


def fake_upi(i):
    """Unique UPI ID."""
    return f'player{i:02d}@ybl'


def fake_email(i):
    """Unique email."""
    return f'player{i:02d}@kuberaa.com'


# ═══════════════════════════════════════════════════════════
# STEP 1: CLEANUP
# ═══════════════════════════════════════════════════════════
def cleanup_old():
    print("\n" + "=" * 60)
    print("STEP 1: PURANA #13 DELETE")
    print("=" * 60)

    old = Tournament.objects.filter(serial_number=13).first()
    if old:
        print(f"🗑️  Deleting: #{old.display_id} — {old.title}")
        old.delete()
        print("✅ Deleted")
    else:
        print("⏭️  #13 nahi mila")


# ═══════════════════════════════════════════════════════════
# STEP 2: TOURNAMENT + ROOM + MATCH
# ═══════════════════════════════════════════════════════════
def create_tournament():
    print("\n" + "=" * 60)
    print("STEP 2: TOURNAMENT + ROOM + MATCH")
    print("=" * 60)

    now = timezone.now()

    tournament = Tournament.objects.create(
        title='FF TEST — 13',
        description='Real OCR test tournament with 32 players',
        rules='Fair play only',
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
        notes='Real OCR test room',
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
    print(f"   🔑 ROOM: {room.room_id} / {room.room_password}")
    print(f"✅ Match ID: {match.id}")

    return tournament, match


# ═══════════════════════════════════════════════════════════
# STEP 3: 32 USERS + REGISTER
# ═══════════════════════════════════════════════════════════
def create_users(tournament):
    print("\n" + "=" * 60)
    print("STEP 3: 32 USERS REGISTER (FAKE UID/UPI/MOBILE)")
    print("=" * 60)

    users = []

    for i, (name, kills, rank) in enumerate(SCREENSHOT_PLAYERS, start=1):
        is_me = (name == MY_FF_NAME)

        if is_me:
            email = MY_EMAIL
            mobile = MY_MOBILE
            uid = MY_UID
            upi = MY_UPI
            display = MY_NAME
        else:
            email = fake_email(i)
            mobile = fake_mobile(i)
            uid = fake_uid(i)
            upi = fake_upi(i)
            display = name

        user, _ = User.objects.get_or_create(
            email=email,
            defaults={
                'display_name': display,
                'mobile_number': mobile,
                'upi_id': upi,
                'free_fire_uid': uid,
                'free_fire_name': name,
                'role': User.Role.USER,
                'status': User.Status.ACTIVE,
            },
        )

        # ✅ Always update (fresh setup)
        user.display_name = display
        user.mobile_number = mobile
        user.upi_id = upi
        user.free_fire_uid = uid
        user.free_fire_name = name
        user.set_password(PASSWORD)
        user.save()

        # ✅ Register
        reg, _ = Registration.objects.get_or_create(
            tournament=tournament,
            user=user,
            defaults={
                'free_fire_uid': uid,
                'free_fire_name': name,
                'user_upi_id': upi,
                'user_mobile': mobile,
                'status': Registration.Status.CONFIRMED,
                'can_play': True,
            },
        )
        reg.status = Registration.Status.CONFIRMED
        reg.can_play = True
        reg.save()

        users.append({
            'user': user,
            'name': name,
            'uid': uid,
            'mobile': mobile,
            'upi': upi,
            'email': email,
            'kills': kills,
            'rank': rank,
            'is_me': is_me,
        })

        marker = "🌟" if is_me else "  "
        print(f"{marker} {i:2}. {name:22} | UID: {uid} | {mobile} | {upi}")

    print(f"\n✅ {len(users)} users registered!")
    return users


# ═══════════════════════════════════════════════════════════
# ✅ STEP 4: ADITYA KA RESULT PEHLE SE SET (WINNER 🏆)
# ═══════════════════════════════════════════════════════════
def set_aditya_winner(match):
    print("\n" + "=" * 60)
    print("STEP 4: ADITYA ALREADY WINNER 🏆")
    print("=" * 60)

    user = User.objects.get(email=MY_EMAIL)

    entry_fee = match.tournament.entry_fee
    per_kill = calculate_per_kill_prize(entry_fee)
    prize = calculate_prize_amount(entry_fee, MY_KILLS)
    score = calculate_score(MY_KILLS, MY_RANK)

    Result.objects.update_or_create(
        match=match,
        user=user,
        defaults={
            'free_fire_uid': user.free_fire_uid,
            'player_name': user.free_fire_name,
            'kills': MY_KILLS,
            'placement': MY_RANK,
            'score': score,
            'prize_amount': prize,
            'per_kill_prize': per_kill,
            'entry_fee': entry_fee,
            'verification_status': Result.VerificationStatus.PUBLISHED,
            'published_at': timezone.now(),
        },
    )

    print(f"✅ Aditya ka result set:")
    print(f"   Name: {user.free_fire_name}")
    print(f"   UID: {user.free_fire_uid}")
    print(f"   Mobile: {user.mobile_number}")
    print(f"   UPI: {user.upi_id}")
    print(f"   Rank: #{MY_RANK}")
    print(f"   Kills: {MY_KILLS}")
    print(f"   Prize: ₹{prize}")
    print(f"   Status: PUBLISHED ✅")


# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════
def main():
    print("\n" + "█" * 60)
    print("█  FINAL SETUP — MATCH #13 + ADITYA WINNER 🏆")
    print("█" * 60)

    cleanup_old()
    tournament, match = create_tournament()
    users = create_users(tournament)
    set_aditya_winner(match)

    print("\n" + "█" * 60)
    print("█  ✅ SETUP COMPLETE")
    print("█" * 60)

    print(f"\n📱 TOURNAMENT:")
    print(f"   #{tournament.display_id} — {tournament.title}")
    print(f"   Tournament ID: {tournament.id}")
    print(f"   Match ID: {match.id}")
    print(f"   Room: 98765432 / abcd123")
    print(f"   Players: {len(users)} registered")

    print(f"\n🏆 ADITYA (ALREADY WINNER):")
    print(f"   Email: {MY_EMAIL}")
    print(f"   Password: {PASSWORD}")
    print(f"   FF Name: {MY_FF_NAME}")
    print(f"   UID: {MY_UID}")
    print(f"   Mobile: {MY_MOBILE}")
    print(f"   UPI: {MY_UPI}")
    print(f"   Result: #{MY_RANK}, {MY_KILLS} kills — PUBLISHED ✅")

    print(f"\n📊 32 PLAYERS (FAKE DATA):")
    print(f"   UIDs: 200000001 - 200000032")
    print(f"   Mobiles: 7000000002 - 7000000033")
    print(f"   UPIs: player01@ybl - player32@ybl")
    print(f"   Emails: player01@kuberaa.com - player32@kuberaa.com")

    print(f"\n📸 AB YE KARO — ADMIN FRONTEND SE:")
    print(f"   1. Flutter app kholo (admin login)")
    print(f"   2. Match #{match.id} → 'Upload Result' button")
    print(f"   3. Screenshot upload karo (Free Fire wala)")
    print(f"   4. ✅ ML Kit OCR chalega — 32 players extract")
    print(f"   5. Aditya skip hoga (already winner hai)")
    print(f"   6. Baaki 31 players ka result banega")
    print(f"   7. 'UPLOAD RESULT' + 'PUBLISH' dabao")
    print(f"   8. User app pe check karo: {MY_EMAIL} / {PASSWORD}")

    print(f"\n🌟 FUTURE MEIN (REAL DATA):")
    print(f"   - Real players ke saath same script chalega")
    print(f"   - UID/UPI/Mobile real honge (database se match honge)")
    print(f"   - OCR se real data extract hoga")


if __name__ == '__main__':
    main()