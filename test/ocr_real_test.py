# C:\Kuberaa\backend\test\ocr_real_test.py
"""
REAL OCR TEST — Google Vision + Free Fire Screenshot
=====================================================
- Aditya ka account (email + mobile) 
- Screenshot upload → Google Vision OCR
- 32 players extract
- Aditya ko 5 kills (manual override)
- Admin panel mein result declare karne ke liye ready
"""

import os
import sys
import django
import re
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kuberaa.settings')
django.setup()

from django.utils import timezone
from apps.users.models import User
from apps.tournaments.models import Tournament, Registration, MatchRoom
from apps.matches.models import Match
from core.ocr.ocr_service import OCRService


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

# ✅ Aditya ke kills (manual override)
MY_KILLS = 5

# ✅ Screenshot path
SCREENSHOT_PATH = r'C:\Kuberaa\backend\test\freefire_screenshot.jpg'


# ═══════════════════════════════════════════════════════════
# STEP 1: SCREENSHOT CHECK
# ═══════════════════════════════════════════════════════════
def check_screenshot():
    print("\n" + "=" * 60)
    print("STEP 1: SCREENSHOT CHECK")
    print("=" * 60)

    if not os.path.exists(SCREENSHOT_PATH):
        print(f"\n❌ Screenshot NOT FOUND: {SCREENSHOT_PATH}")
        print(f"\n💡 Kya karo:")
        print(f"   1. Apni Free Fire screenshot save karo:")
        print(f"      {SCREENSHOT_PATH}")
        print(f"   2. Ya SCREENSHOT_PATH mein sahi path daalo")
        return False

    size_kb = os.path.getsize(SCREENSHOT_PATH) / 1024
    print(f"✅ Screenshot found: {size_kb:.1f} KB")
    return True


# ═══════════════════════════════════════════════════════════
# STEP 2: GOOGLE VISION OCR RUN
# ═══════════════════════════════════════════════════════════
def run_ocr():
    print("\n" + "=" * 60)
    print("STEP 2: GOOGLE VISION OCR")
    print("=" * 60)

    try:
        result = OCRService.extract_from_image(SCREENSHOT_PATH)
        print(f"\n✅ OCR done!")
        print(f"   Confidence: {result['confidence']:.2%}")
        print(f"   Text length: {len(result['raw_text'])} chars")

        print(f"\n📄 RAW TEXT:")
        print("─" * 60)
        print(result['raw_text'][:2000])  # Pehle 2000 chars
        print("─" * 60)

        return result

    except Exception as e:
        print(f"❌ OCR error: {e}")
        import traceback
        traceback.print_exc()
        return None


# ═══════════════════════════════════════════════════════════
# STEP 3: PARSE PLAYERS FROM OCR TEXT
# ═══════════════════════════════════════════════════════════
def parse_players_from_ocr(raw_text):
    """Free Fire screenshot text se saare players extract karo."""
    print("\n" + "=" * 60)
    print("STEP 3: PARSE PLAYERS FROM OCR")
    print("=" * 60)

    players = []
    lines = [l.strip() for l in raw_text.split('\n') if l.strip()]

    # ✅ Pattern: "Name X Eliminations"
    pattern = re.compile(
        r'(.+?)\s+(\d+)\s*[Ee]liminations?',
        re.IGNORECASE,
    )

    # ✅ Rank markers — jab "1", "2", "3"... ya "1st", "2nd" mile
    rank_pattern = re.compile(r'^(\d)\s*$')

    current_rank = 0

    for line in lines:
        # Rank check
        rank_match = rank_pattern.match(line.strip())
        if rank_match:
            r = int(rank_match.group(1))
            if 1 <= r <= 8:
                current_rank = r
            continue

        # Player match
        match = pattern.search(line)
        if match:
            name = match.group(1).strip()
            kills = int(match.group(2))

            # Clean name
            name = re.sub(r'^[\d\.\s\)]+', '', name)  # leading junk
            name = re.sub(r'[\s\)]+$', '', name)      # trailing junk
            name = name.strip()

            if name and 2 <= len(name) <= 30 and kills < 100:
                players.append({
                    'name': name,
                    'kills': kills,
                    'rank': current_rank if current_rank > 0 else 99,
                })

    print(f"\n📊 {len(players)} players extracted from OCR:")
    for i, p in enumerate(players, 1):
        marker = "🌟" if 'prime' in p['name'].lower() else "  "
        print(f"  {marker} {i:2}. {p['name']:25} | {p['kills']} kills | Rank #{p['rank']}")

    return players


# ═══════════════════════════════════════════════════════════
# STEP 4: CLEANUP #13
# ═══════════════════════════════════════════════════════════
def cleanup_old():
    print("\n" + "=" * 60)
    print("STEP 4: PURANA #13 DELETE")
    print("=" * 60)

    old = Tournament.objects.filter(serial_number=13).first()
    if old:
        print(f"🗑️  Deleting: #{old.display_id}")
        old.delete()
        print("✅ Deleted")
    else:
        print("⏭️  Not found")


# ═══════════════════════════════════════════════════════════
# STEP 5: TOURNAMENT + MATCH + ROOM
# ═══════════════════════════════════════════════════════════
def create_tournament():
    print("\n" + "=" * 60)
    print("STEP 5: TOURNAMENT + MATCH + ROOM")
    print("=" * 60)

    now = timezone.now()

    tournament = Tournament.objects.create(
        title='FF TEST — 13',
        description='Real OCR test',
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
        notes='OCR test room',
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

    print(f"✅ #{tournament.display_id} | Tournament ID: {tournament.id}")
    print(f"✅ Room: {room.room_id} / {room.room_password}")
    print(f"✅ Match ID: {match.id}")

    return tournament, match


# ═══════════════════════════════════════════════════════════
# STEP 6: USERS REGISTER (OCR players)
# ═══════════════════════════════════════════════════════════
def create_users(tournament, ocr_players):
    print("\n" + "=" * 60)
    print("STEP 6: USERS REGISTER (OCR players)")
    print("=" * 60)

    users = []
    used_names = set()

    # ✅ Aditya pehle
    my_user, _ = User.objects.get_or_create(
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
    my_user.display_name = MY_NAME
    my_user.mobile_number = MY_MOBILE
    my_user.upi_id = MY_UPI
    my_user.free_fire_uid = MY_UID
    my_user.free_fire_name = MY_FF_NAME
    my_user.set_password(PASSWORD)
    my_user.save()

    reg, _ = Registration.objects.get_or_create(
        tournament=tournament,
        user=my_user,
        defaults={
            'free_fire_uid': MY_UID,
            'free_fire_name': MY_FF_NAME,
            'user_upi_id': MY_UPI,
            'user_mobile': MY_MOBILE,
            'status': Registration.Status.CONFIRMED,
            'can_play': True,
        },
    )
    reg.status = Registration.Status.CONFIRMED
    reg.can_play = True
    reg.save()

    users.append({
        'user': my_user,
        'name': MY_FF_NAME,
        'uid': MY_UID,
        'email': MY_EMAIL,
        'mobile': MY_MOBILE,
        'upi': MY_UPI,
        'kills': MY_KILLS,        # ✅ 5 kills manual
        'rank': 1,
        'is_me': True,
    })
    used_names.add(MY_FF_NAME.lower())
    print(f"🌟 {MY_FF_NAME:22} | UID: {MY_UID} | {MY_KILLS} kills (MANUAL)")

    # ✅ OCR se mile baaki players
    for i, p in enumerate(ocr_players, start=1):
        name = p['name']
        kills = p['kills']
        rank = p['rank']

        # Skip agar already added
        if name.lower() in used_names:
            continue

        # Skip agar prime_aditya jaisa hai
        if 'prime' in name.lower() and 'aditya' in name.lower():
            continue

        used_names.add(name.lower())

        # Fake data
        email = f'ocrplayer{i:02d}@test.com'
        mobile = f'98765{i:05d}'[-10:]
        uid = f'{300000000 + i}'
        upi = f'ocrplayer{i:02d}@paytm'

        user, _ = User.objects.get_or_create(
            email=email,
            defaults={
                'display_name': name,
                'mobile_number': mobile,
                'upi_id': upi,
                'free_fire_uid': uid,
                'free_fire_name': name,
                'role': User.Role.USER,
                'status': User.Status.ACTIVE,
            },
        )
        user.display_name = name
        user.mobile_number = mobile
        user.upi_id = upi
        user.free_fire_uid = uid
        user.free_fire_name = name
        user.set_password(PASSWORD)
        user.save()

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
            'email': email,
            'mobile': mobile,
            'upi': upi,
            'kills': kills,
            'rank': rank,
            'is_me': False,
        })
        print(f"   {name:22} | UID: {uid} | {kills} kills | Rank #{rank}")

    print(f"\n✅ Total {len(users)} users registered!")
    return users


# ═══════════════════════════════════════════════════════════
# STEP 7: RESULT DECLARE (OCR data)
# ═══════════════════════════════════════════════════════════
def declare_results(match, users):
    print("\n" + "=" * 60)
    print("STEP 7: RESULT DECLARE (OCR + Manual)")
    print("=" * 60)

    from apps.results.models import Result
    from apps.results.utils.prize_calculator import (
        calculate_per_kill_prize,
        calculate_prize_amount,
        calculate_score,
    )

    entry_fee = match.tournament.entry_fee
    per_kill = calculate_per_kill_prize(entry_fee)

    for u in users:
        user = u['user']
        kills = u['kills']
        placement = u['rank']

        prize = calculate_prize_amount(entry_fee, kills)
        score = calculate_score(kills, placement)

        Result.objects.update_or_create(
            match=match,
            user=user,
            defaults={
                'free_fire_uid': user.free_fire_uid,
                'player_name': user.free_fire_name,
                'kills': kills,
                'placement': placement,
                'score': score,
                'prize_amount': prize,
                'per_kill_prize': per_kill,
                'entry_fee': entry_fee,
                'verification_status': Result.VerificationStatus.PUBLISHED,
                'published_at': timezone.now(),
            },
        )

        marker = "🏆" if u['is_me'] else "  "
        print(f"{marker} {user.free_fire_name:22} | #{placement} | "
              f"{kills} kills | ₹{prize}")

    print(f"\n✅ {len(users)} results published!")


# ═══════════════════════════════════════════════════════════
# STEP 8: MATCH COMPLETE
# ═══════════════════════════════════════════════════════════
def complete_match(match):
    print("\n" + "=" * 60)
    print("STEP 8: MATCH COMPLETE")
    print("=" * 60)

    match.status = Match.Status.COMPLETED
    match.save()

    match.tournament.status = Tournament.Status.COMPLETED
    match.tournament.save()

    print(f"✅ Match: {match.status}")
    print(f"✅ Tournament: {match.tournament.status}")


# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════
def main():
    print("\n" + "█" * 60)
    print("█  REAL OCR TEST — GOOGLE VISION + FREE FIRE")
    print("█" * 60)

    # Step 1
    if not check_screenshot():
        return

    # Step 2
    ocr_result = run_ocr()
    if not ocr_result:
        print("\n❌ OCR failed")
        return

    # Step 3
    ocr_players = parse_players_from_ocr(ocr_result['raw_text'])

    if not ocr_players:
        print("\n❌ Koi player OCR se nahi mila")
        return

    # Step 4
    cleanup_old()

    # Step 5
    tournament, match = create_tournament()

    # Step 6
    users = create_users(tournament, ocr_players)

    # Step 7
    declare_results(match, users)

    # Step 8
    complete_match(match)

    # ═══════════════════════════════════════════════════════
    # SUMMARY
    # ═══════════════════════════════════════════════════════
    print("\n" + "█" * 60)
    print("█  ✅ ALL DONE")
    print("█" * 60)

    print(f"\n📱 TOURNAMENT:")
    print(f"   #{tournament.display_id} — {tournament.title}")
    print(f"   Tournament ID: {tournament.id}")
    print(f"   Match ID: {match.id}")

    print(f"\n🌟 ADITYA:")
    print(f"   Email: {MY_EMAIL}")
    print(f"   Mobile: {MY_MOBILE}")
    print(f"   UPI: {MY_UPI}")
    print(f"   UID: {MY_UID}")
    print(f"   Kills: {MY_KILLS} (manual override)")
    print(f"   Rank: #1")

    print(f"\n🔗 ADMIN LINK:")
    print(f"   http://127.0.0.1:8000/admin/matches/match/{match.id}/change/")

    print(f"\n✅ AB YE KARO:")
    print(f"   1. Flutter app restart karo")
    print(f"   2. Login: {MY_EMAIL} / {PASSWORD}")
    print(f"   3. My Matches → Match #13")
    print(f"   4. View Result — Aditya dikhna chahiye 5 kills ke saath")


if __name__ == '__main__':
    main()