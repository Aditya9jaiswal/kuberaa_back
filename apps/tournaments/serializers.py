from rest_framework import serializers
from .models import Tournament, Registration


class TournamentSerializer(serializers.ModelSerializer):
    display_id = serializers.CharField(read_only=True)
    is_registration_open = serializers.BooleanField(read_only=True)
    is_full = serializers.BooleanField(read_only=True)
    slots_left = serializers.IntegerField(read_only=True)
    my_registration = serializers.SerializerMethodField()

    class Meta:
        model = Tournament
        fields = [
            'id',
            'serial_number',
            'display_id',
            'title',
            'description',
            'rules',
            'prize_info',
            'tournament_type',  # ✅ NAYA
            'tournament_date',
            'start_time',
            'registration_start',
            'registration_end',
            'maximum_participants',
            'current_participants',
            'entry_fee',
            'upi_id',
            'upi_name',
            'status',
            'is_registration_open',
            'is_full',
            'slots_left',
            'my_registration',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'serial_number',
            'current_participants',
            'created_at',
            'updated_at',
        ]

    def get_my_registration(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None

        reg = Registration.objects.filter(
            tournament=obj,
            user=request.user,
        ).first()

        if not reg:
            return None

        return {
            'id': str(reg.id),
            'status': reg.status,
            'can_play': reg.can_play,
            'user_upi_id': reg.user_upi_id,
            'user_mobile': reg.user_mobile,
            'free_fire_uid': reg.free_fire_uid,
            'free_fire_name': reg.free_fire_name,
            'transaction_id': getattr(reg, 'transaction_id', ''),
            'created_at': reg.created_at.isoformat() if reg.created_at else None,
        }


class TournamentListSerializer(serializers.ModelSerializer):
    display_id = serializers.CharField(read_only=True)
    is_registration_open = serializers.BooleanField(read_only=True)
    slots_left = serializers.IntegerField(read_only=True)
    my_registration = serializers.SerializerMethodField()  # ✅ ADD

    class Meta:
        model = Tournament
        fields = [
            'id',
            'display_id',
            'title',
            'tournament_type',  # ✅ NAYA
            'tournament_date',
            'start_time',
            'entry_fee',
            'upi_id',
            'upi_name',
            'maximum_participants',
            'current_participants',
            'status',
            'prize_info',
            'is_registration_open',
            'is_full',  # ✅ ADD
            'slots_left',
            'my_registration',  # ✅ ADD
        ]

    def get_my_registration(self, obj):
        """Home screen ke liye — my_registration bhi chahiye"""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None

        reg = Registration.objects.filter(
            tournament=obj,
            user=request.user,
        ).first()

        if not reg:
            return None

        return {
            'id': str(reg.id),
            'status': reg.status,
            'can_play': reg.can_play,
            'user_upi_id': reg.user_upi_id,
            'user_mobile': reg.user_mobile,
            'free_fire_uid': reg.free_fire_uid,
            'free_fire_name': reg.free_fire_name,
        }


class RegistrationSerializer(serializers.ModelSerializer):
    tournament_title = serializers.CharField(source='tournament.title', read_only=True)
    tournament_display_id = serializers.CharField(source='tournament.display_id', read_only=True)

    class Meta:
        model = Registration
        fields = [
            'id',
            'tournament',
            'tournament_title',
            'tournament_display_id',
            'user',
            'free_fire_uid',
            'free_fire_name',
            'user_upi_id',
            'user_mobile',
            'status',
            'can_play',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'user', 'status', 'can_play', 'created_at', 'updated_at']


class RegistrationListSerializer(serializers.ModelSerializer):
    tournament_display_id = serializers.CharField(source='tournament.display_id', read_only=True)
    tournament_title = serializers.CharField(source='tournament.title', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)

    class Meta:
        model = Registration
        fields = [
            'id',
            'tournament',
            'tournament_display_id',
            'tournament_title',
            'user_email',
            'free_fire_uid',
            'free_fire_name',
            'user_upi_id',
            'user_mobile',
            'status',
            'can_play',
            'created_at',
        ]


class MyRegistrationDetailSerializer(serializers.ModelSerializer):
    tournament = serializers.SerializerMethodField()
    room = serializers.SerializerMethodField()
    registration_id = serializers.UUIDField(source='id', read_only=True)

    class Meta:
        model = Registration
        fields = [
            'registration_id',
            'status',
            'can_play',
            'free_fire_uid',
            'free_fire_name',
            'user_upi_id',
            'user_mobile',
            'created_at',
            'tournament',
            'room',
        ]

    def get_tournament(self, obj):
        t = obj.tournament
        return {
            'id': str(t.id),
            'display_id': t.display_id,
            'title': t.title,
            'tournament_type': t.tournament_type,  # ✅ ADD
            'entry_fee': str(t.entry_fee),
            'upi_id': t.upi_id,
            'upi_name': t.upi_name,
            'tournament_date': str(t.tournament_date),
            'start_time': t.start_time.isoformat() if t.start_time else None,
            'status': t.status,
            'prize_info': t.prize_info,
            'current_participants': t.current_participants,
            'maximum_participants': t.maximum_participants,
        }

    def get_room(self, obj):
        if not obj.can_play:
            return None
        try:
            room = obj.tournament.match_room
            return {
                'room_id': room.room_id,
                'room_password': room.room_password,
                'scheduled_at': room.scheduled_at.isoformat() if room.scheduled_at else None,
            }
        except Exception:
            return None