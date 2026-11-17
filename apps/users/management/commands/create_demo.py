from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
import random

from apps.tournaments.models import Tournament, Registration, PrizeConfig
from apps.matches.models import Match
from apps.results.models import Result
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = 'Create simple demo data'

    def handle(self, *args, **kwargs):
        self.stdout.write('=' * 60)
        self.stdout.write('🚀 KUBERAA DEMO DATA CREATOR')
        self.stdout.write('=' * 60)

        # ═══════════════════════════════════════════════════════
        # USERS
        # ═══════════════════════════════════════════════════════
        users = []
        for i in range(1, 6):
            email = f'demo{i}@test.com'
            u, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'display_name': f'Player {i}',
                    'mobile_number': f'98765432{i:02d}',
                    'free_fire_uid': f'12345678{i}',
                    'free_fire_name': f'ProGamer{i}',
                    'upi_id': f'player{i}@paytm',
                    'status': 'ACTIVE',
                    'role': 'USER',
                }
            )
            if created:
                u.set_password('demo123')
                u.save()
            users.append(u)

        self.stdout.write(f'✅ {len(users)} users ready')
        for u in users:
            self.stdout.write(f'   📧 {u.email}  |  🔑 demo123')

        # ═══════════════════════════════════════════════════════
        # TOURNAMENT
        # ═══════════════════════════════════════════════════════
        t = Tournament.objects.create(
            title='[DEMO] Test Tournament',
            description='Demo tournament for testing',
            rules='Fair play only',
            prize_info='₹15/kill + bonuses',
            entry_fee=Decimal('10.00'),
            upi_id='kuberaa@upi',
            upi_name='Kuberaa Gaming',
            tournament_type='FREEFIRE',
            tournament_date=timezone.now().date(),
            start_time=timezone.now() - timedelta(minutes=10),
            registration_start=timezone.now() - timedelta(hours=1),
            registration_end=timezone.now() + timedelta(hours=1),
            maximum_participants=50,
            status='LIVE',
        )
        PrizeConfig.objects.get_or_create(
            tournament=t,
            defaults={
                'per_kill_amount': 15,
                'first_place_bonus': 500,
                'second_place_bonus': 300,
                'third_place_bonus': 150,
            }
        )
        self.stdout.write(f'✅ Tournament created: {t.title}')

        # ═══════════════════════════════════════════════════════
        # MATCH — room_release_time added
        # ═══════════════════════════════════════════════════════
        now = timezone.now()
        m = Match.objects.create(
            tournament=t,
            match_number=1,
            title='Match 1',
            room_id='12345678',
            room_password='pass123',
            scheduled_start_time=now - timedelta(minutes=5),
            room_release_time=now - timedelta(minutes=10),  # ✅ REQUIRED FIELD
            max_participants=50,
            entry_fee=Decimal('10.00'),
            status='LIVE',
        )
        self.stdout.write(f'✅ Match created: Match #{m.match_number}')
        self.stdout.write(f'   🚪 Room ID: {m.room_id}')
        self.stdout.write(f'   🔑 Password: {m.room_password}')

        # ═══════════════════════════════════════════════════════
        # REGISTRATIONS + RESULTS
        # ═══════════════════════════════════════════════════════
        for i, u in enumerate(users):
            Registration.objects.create(
                tournament=t,
                match=m,
                user=u,
                user_mobile=u.mobile_number,
                free_fire_uid=u.free_fire_uid,
                free_fire_name=u.free_fire_name,
                user_upi_id=u.upi_id,
                amount=Decimal('10.00'),
                status=Registration.Status.CONFIRMED,
                can_play=True,
            )

            kills = random.randint(0, 15)
            rank = i + 1
            prize = kills * 15
            if rank == 1:
                prize += 500
            elif rank == 2:
                prize += 300
            elif rank == 3:
                prize += 150

            Result.objects.create(
                match=m,
                tournament=t,
                user=u,
                kills=kills,
                rank=rank,
                placement=rank,
                prize=Decimal(str(prize)),
            )

        self.stdout.write(f'✅ {len(users)} registrations + results created')
        self.stdout.write('')
        self.stdout.write('=' * 60)
        self.stdout.write(self.style.SUCCESS('🎉 DEMO DATA READY!'))
        self.stdout.write('=' * 60)
        self.stdout.write(f'🔴 LIVE Matches: 1')
        self.stdout.write(f'🏆 Tournaments: 1')
        self.stdout.write(f'👥 Users: 5')
        self.stdout.write(f'🏅 Results: 5')