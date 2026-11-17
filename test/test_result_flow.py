# C:\Kuberaa\backend\test\test_result_flow.py
"""
FINAL TEST SCRIPT — ADMIN RESULT UPLOAD + WINNING SOUND
=======================================================
- Total 48 Players
- Rank 1 to 48 Strict Sequence
- Admin Result Upload Simulate karega (API jaisa logic)
- Winning Notification + Sound bhejega
"""

import sys
import os
from datetime import timedelta
from decimal import Decimal

# ═══════════════════════════════════════════════════════════
# ROOT FOLDER PATH FIX
# ═══════════════════════════════════════════════════════════
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

# ═══════════════════════════════════════════════════════════
# DJANGO SETUP
# ═══════════════════════════════════════════════════════════
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kuberaa.settings')

import django
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
from apps.results.cache_utils import (
    invalidate_match_results_cache,
    invalidate_notifications_cache,
)

# ✅ FCM & Notification imports
from firebase_admin import messaging
from apps.payments.models import UserNotification

# ═══════════════════════════════════════════════════════════
# CONFIG (YOUR PROFILE - RANK 1)
# ═══════════════════════════════════════════════════════════
MY_EMAIL = 'adityajaiswal1734@gmail.com'
MY_MOBILE = '9685778431'
MY_NAME = 'Aditya'
MY_UID = '2114130469916792832'
MY_UPI = 'adityajaiswal1734@paytm'
PASSWORD = 'test1234'

# ═══════════════════════════════════════════════════════════
# 48 PLAYERS LIST (SCREENSHOT KE HISAB SE 1 SE 48 TAK)
# Format: (FF Name, FF UID, Kills, Placement)
# ═══════════════════════════════════════════════════════════
PLAYERS_DATA = [
    # Rank 2 to 7
    ("CHANDU DON!!", "8529637410", 3, 2),
    ("A.‚beast", "9517532580", 2, 3),
    ("?Rex*Dev", "7894561230", 3, 4),
    ("Kanha§!ngh", "4561237890", 1, 5),
    ("+JAYHIND+", "1237894560", 2, 6),
    ("NY@0987", "9871236540", 1, 7),
    # Rank 8 to 14
    ("zend..444", "7418529630", 11, 8),
    ("N046d01e6239", "3692581470", 1, 9),
    ("LEGEND", "2581473690", 0, 10),
    ("DJ Raj YT", "1472583690", 2, 11),
    ("Ax GHOST", "9638527410", 2, 12),
    ("MR RAJ.FF", "8527419630", 11, 13),
    ("UC OBITO", "7419638520", 5, 14),
    # Rank 15 to 21
    ("KONDAMSTAR", "1593574862", 0, 15),
    ("Darbar-bapu5", "7531594862", 3, 16),
    ("MR RAVAN-01", "9513574862", 0, 17),
    ("tpbosssshgdhd", "3579514862", 1, 18),
    ("Sk FARDIN", "1597534862", 0, 19),
    ("____flexx", "7539514862", 3, 20),
    ("NkcChamar", "9517534862", 2, 21),
    # Rank 22 to 28
    ("?LK?D A D A", "3571594862", 1, 22),
    ("AKSHAT", "1593577531", 7, 23),
    ("BOSS_SUMAN", "7531597531", 3, 24),
    ("KellyJa26015", "9513577531", 0, 25),
    ("NG-FA4HAN", "3579517531", 1, 26),
    ("EgoPARIME", "1597537531", 4, 27),
    ("BOSS_SUMAN", "7539517531", 3, 28),
    # Rank 29 to 35
    ("LX DAD", "9517537531", 0, 29),
    ("UK VOKAS", "3571597531", 1, 30),
    ("SOME CHANGER", "1593571597", 0, 31),
    ("King4q4l2k", "7531591597", 0, 32),
    ("LORDYuvRaj", "9513571597", 0, 33),
    ("Adityas Royal", "3579511597", 2, 34),
    ("ANGEL", "1597531597", 1, 35),
    # Rank 36 to 42
    ("Gunn5C6a4", "7539511597", 0, 36),
    ("Deep OP", "9517531597", 0, 37),
    ("Legendry", "3571591597", 0, 38),
    ("Rangeeli", "1593573579", 0, 39),
    ("GYANGAMING", "7531593579", 0, 40),
    ("Mickey ???", "9513573579", 0, 41),
    ("Sigh6v3#4K3", "3579513579", 0, 42),
    # Rank 43 to 46
    ("Anti969r5", "1597533579", 0, 43),
    ("DRAGON", "7539513579", 0, 44),
    ("January8798", "9517533579", 0, 45),
    ("Dairy Milk !", "3571593579", 0, 46),
    # Rank 47 to 48
    ("NoobMaster", "1593579513", 0, 47),
    ("TotalGaming", "7531599513", 0, 48),
]

# ═══════════════════════════════════════════════════════════
# STEP 1: CLEANUP
# ═══════════════════════════════════════════════════════════
def cleanup_old():
    print("\n" + "=" * 60)
    print("STEP 1: CLEANUP — PURANA #13 DELETE")
    print("=" * 60)

    old = Tournament.objects.filter(serial_number=13).first()
    if old:
        print(f"🗑️  Deleting #{old.display_id} — {old.title}")
        old.delete()
        print("✅ Deleted")
    else:
        print("⏭️  #13 not found")

# ═══════════════════════════════════════════════════════════
# STEP 2: TOURNAMENT CREATE
# ═══════════════════════════════════════════════════════════
def create_tournament():
    print("\n" + "=" * 60)
    print("STEP 2: NAYA TOURNAMENT (48 SLOTS)")
    print("=" * 60)

    now = timezone.now()

    tournament = Tournament.objects.create(
        title='FF TEST — 13',
        description='Test tournament 48 players',
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

    MatchRoom.objects.create(
        tournament=tournament,
        room_id='98765432',
        room_password='abcd123',
        scheduled_at=now + timedelta(minutes=30),
        notes='Test room',
    )

    print(f"✅ Tournament Created: {tournament.title}")
    return tournament

# ═══════════════════════════════════════════════════════════
# STEP 3: MATCH CREATE
# ═══════════════════════════════════════════════════════════
def create_match(tournament):
    print("\n" + "=" * 60)
    print("STEP 3: MATCH CREATE")
    print("=" * 60)

    now = timezone.now()

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

    print(f"✅ Match Created! Max Participants: {match.max_participants}")
    return match

# ═══════════════════════════════════════════════════════════
# STEP 4: USERS + REGISTER
# ═══════════════════════════════════════════════════════════
def create_and_register(tournament):
    print("\n" + "=" * 60)
    print("STEP 4: REGISTERING 48 PLAYERS")
    print("=" * 60)

    # 1. Aapka Account
    my_user, _ = User.objects.get_or_create(
        email=MY_EMAIL,
        defaults={
            'display_name': MY_NAME,
            'mobile_number': MY_MOBILE,
            'upi_id': MY_UPI,
            'free_fire_uid': MY_UID,
            'free_fire_name': MY_NAME,
            'role': User.Role.USER,
            'status': User.Status.ACTIVE,
        },
    )
    my_user.set_password(PASSWORD)
    my_user.save()

    Registration.objects.get_or_create(
        tournament=tournament,
        user=my_user,
        defaults={
            'free_fire_uid': MY_UID,
            'free_fire_name': MY_NAME,
            'user_upi_id': MY_UPI,
            'user_mobile': MY_MOBILE,
            'status': Registration.Status.CONFIRMED,
            'can_play': True,
        },
    )
    users = [my_user]
    print(f"🌟 ✅ {my_user.email} (UID: {MY_UID}) - Aapka Account [Rank 1]")

    # 2. Screenshot Wale Players (47 Players)
    for idx, player in enumerate(PLAYERS_DATA):
        ff_name, ff_uid, _, _ = player
        email = f"player{idx+1}@test.com"
        
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                'display_name': ff_name,
                'free_fire_uid': ff_uid,
                'free_fire_name': ff_name,
                'role': User.Role.USER,
                'status': User.Status.ACTIVE,
            },
        )
        
        if not created:
            user.free_fire_uid = ff_uid
            user.free_fire_name = ff_name
            user.save()

        user.set_password(PASSWORD)
        user.save()

        Registration.objects.get_or_create(
            tournament=tournament,
            user=user,
            defaults={
                'free_fire_uid': ff_uid,
                'free_fire_name': ff_name,
                'status': Registration.Status.CONFIRMED,
                'can_play': True,
            },
        )
        users.append(user)
        
    print(f"\n✅ Total {len(users)} users successfully registered (48/48)!")
    return users

# ═══════════════════════════════════════════════════════════
# ✅ STEP 5: ADMIN RESULT UPLOAD (EXACT LOGIC)
# ═══════════════════════════════════════════════════════════
def add_results(match, users):
    print("\n" + "=" * 60)
    print("STEP 5: ADMIN RESULT UPLOAD (RANK 1 TO 48)")
    print("=" * 60)

    entry_fee = match.tournament.entry_fee
    per_kill = calculate_per_kill_prize(entry_fee)
    total_prize = Decimal('0.00')
    affected_user_ids = []

    # Aapka Result (Rank 1, 2 Kills)
    results_data = [{
        'user': users[0],
        'kills': 2, # Aapke 2 kills
        'placement': 1, # Aapki Rank 1
    }]

    # Baaki 47 Players ka Result
    for idx, player in enumerate(PLAYERS_DATA):
        ff_name, ff_uid, kills, placement = player
        results_data.append({
            'user': users[idx + 1],
            'kills': kills,
            'placement': placement,
        })

    # ✅ ADMIN UPLOAD LOGIC (Jaise AdminResultUploadView karta hai)
    for data in results_data:
        user = data['user']
        kills = data['kills']
        placement = data['placement']

        prize = calculate_prize_amount(entry_fee, kills)
        score = calculate_score(kills, placement)
        points = Result.calculate_points(entry_fee, kills)
        total_prize += prize

        affected_user_ids.append(user.id)

        # Result create/update (Admin Upload jaisa)
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
                'points_earned': points,
                'verification_status': Result.VerificationStatus.PUBLISHED,
                'published_at': timezone.now(),
            },
        )
        
        # ✅ DB Notification (Result Published)
        UserNotification.objects.create(
            user=user, type='result_published',
            title='🏆 Result Announced!',
            message=f'Aapka result aa gaya!\n\nKills: {kills}\nPlacement: #{placement}\nPrize: ₹{prize}',
        )

        # ✅ FCM Push Notification (Result Sound)
        if user.fcm_token:
            try:
                message = messaging.Message(
                    notification=messaging.Notification(
                        title='🏆 Result Announced!',
                        body=f'Kills: {kills}, Prize: ₹{prize}',
                    ),
                    data={
                        'type': 'result_published',
                        'screen': 'result',
                        'match_id': str(match.id),
                    },
                    android=messaging.AndroidConfig(
                        priority='high',
                        notification=messaging.AndroidNotification(
                            channel_id='result_channel_v2',
                            sound='result',
                        ),
                    ),
                    token=user.fcm_token,
                )
                messaging.send(message)
            except Exception as e:
                print(f"❌ Result FCM error to {user.email}: {e}")

    invalidate_match_results_cache(match_id=match.id, user_ids=affected_user_ids)
    
    print(f"\n✅ All 48 Results Uploaded Successfully!")
    print(f"💰 Total Prize Pool: ₹{total_prize}")

# ═══════════════════════════════════════════════════════════
# STEP 6: COMPLETE
# ═══════════════════════════════════════════════════════════
def complete(match):
    print("\n" + "=" * 60)
    print("STEP 6: MATCH COMPLETE")
    print("=" * 60)

    match.status = Match.Status.COMPLETED
    match.save()

    match.tournament.status = Tournament.Status.COMPLETED
    match.tournament.save()

    print(f"✅ Match Status: {match.status}")
    print(f"✅ Tournament Status: {match.tournament.status}")

# ═══════════════════════════════════════════════════════════
# ✅ STEP 7: WINNING NOTIFICATION + SOUND
# ═══════════════════════════════════════════════════════════
def send_winning_notification(match, user):
    print("\n" + "=" * 60)
    print("STEP 7: WINNING NOTIFICATION + SOUND")
    print("=" * 60)

    result = Result.objects.get(match=match, user=user)
    kills = result.kills
    prize = float(result.prize_amount)
    placement = result.placement

    # 1. DB Notification Create karo (App ke andar list ke liye)
    UserNotification.objects.create(
        user=user,
        type='prize_paid',
        title=f'🎉 You Won ₹{prize:.0f}!',
        message=f'Mubarak ho!\n\nKills: {kills}\nPlacement: #{placement}\nPrize: ₹{prize}',
    )
    print(f"✅ DB Winning Notification created")

    # 2. Cache Clear karo
    invalidate_notifications_cache(user.id)
    invalidate_match_results_cache(match.id, user_ids=[user.id])
    print(f"✅ Cache cleared")

    # 3. FCM Push Notification bhejo (Phone pe Winning Sound ke liye)
    if user.fcm_token:
        try:
            message = messaging.Message(
                notification=messaging.Notification(
                    title=f'🎉 You Won ₹{prize:.0f}!',
                    body=f'Kills: {kills}, Placement: #{placement}',
                ),
                data={
                    'type': 'prize_paid',
                    'screen': 'result',
                    'prize_amount': str(prize),
                },
                android=messaging.AndroidConfig(
                    priority='high',
                    notification=messaging.AndroidNotification(
                        channel_id='winning_channel_v2',
                        sound='winning',
                    ),
                ),
                token=user.fcm_token,
            )
            response = messaging.send(message)
            print(f"✅ FCM WINNING SENT! ID: {response}")
        except Exception as e:
            print(f"❌ FCM ERROR: {e}")
    else:
        print("❌ FCM Token missing! App login karo.")

# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════
def main():
    print("\n" + "█" * 60)
    print("█  FINAL TEST — ADMIN UPLOAD FLOW (RANK 1 TO 48)")
    print("█" * 60)

    cleanup_old()
    tournament = create_tournament()
    match = create_match(tournament)
    users = create_and_register(tournament)

    add_results(match, users)   # ✅ Admin Upload Logic
    complete(match)             # ✅ Match Complete

    # ✅ Aditya ko Winning notification bhejo
    send_winning_notification(match, users[0])

    print("\n" + "█" * 60)
    print("█  ✅ ALL DONE — Phone check karo!")
    print("█" * 60)

    print(f"\n🌟 YOUR LOGIN:")
    print(f"   Email: {MY_EMAIL}")
    print(f"   Password: {PASSWORD}")
    print(f"   Result: Rank 1, 2 Kills")

if __name__ == '__main__':
    main()