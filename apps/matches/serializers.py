from rest_framework import serializers
from datetime import timedelta
from .models import Match, MatchParticipant


class MatchSerializer(serializers.ModelSerializer):
    """User-facing — hides room credentials"""
    tournament_title = serializers.CharField(
        source='tournament.title', read_only=True
    )
    tournament_display_id = serializers.CharField(
        source='tournament.display_id', read_only=True
    )
    is_room_available = serializers.BooleanField(read_only=True)
    minutes_until_release = serializers.IntegerField(read_only=True)
    minutes_until_start = serializers.IntegerField(read_only=True)

    class Meta:
        model = Match
        fields = [
            'id', 'tournament', 'tournament_title', 'tournament_display_id',
            'match_number', 'title',
            'scheduled_start_time', 'room_release_time',
            'is_room_available', 'minutes_until_release', 'minutes_until_start',
            'max_participants', 'entry_fee',
            'status',
        ]


class MatchAdminSerializer(serializers.ModelSerializer):
    """Admin — sees everything including room credentials.
    
    Accepts `tournament_id` (UUID) as write-only alias for `tournament`.
    Auto-computes `room_release_time` if missing (5 min before start).
    """
    tournament_id = serializers.UUIDField(write_only=True, required=False)
    tournament_title = serializers.CharField(
        source='tournament.title', read_only=True
    )
    tournament_display_id = serializers.CharField(
        source='tournament.display_id', read_only=True
    )
    is_room_available = serializers.BooleanField(read_only=True)
    minutes_until_release = serializers.IntegerField(read_only=True)
    minutes_until_start = serializers.IntegerField(read_only=True)

    class Meta:
        model = Match
        fields = [
            'id',
            'tournament', 'tournament_id',
            'tournament_title', 'tournament_display_id',
            'match_number', 'title',
            'scheduled_start_time', 'room_release_time',
            'is_room_available', 'minutes_until_release',
            'minutes_until_start',
            'room_id', 'room_password', 'room_notes',
            'max_participants', 'entry_fee',
            'status', 'created_by', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'status',
            'tournament', 'created_by',
        ]

    def validate(self, attrs):
        """Auto-fill room_release_time + validate match_number unique."""
        # Auto room_release_time if missing
        if not attrs.get('room_release_time'):
            start = attrs.get('scheduled_start_time')
            if start:
                attrs['room_release_time'] = start - timedelta(minutes=5)
            else:
                raise serializers.ValidationError({
                    'scheduled_start_time': 'This field is required.'
                })

        # Resolve tournament_id → tournament
        tournament_id = attrs.pop('tournament_id', None)
        if tournament_id:
            from apps.tournaments.models import Tournament
            try:
                tournament = Tournament.objects.get(id=tournament_id)
            except Tournament.DoesNotExist:
                raise serializers.ValidationError({
                    'tournament_id': f'Tournament with id {tournament_id} does not exist.'
                })
            attrs['tournament'] = tournament
        elif not self.instance and not attrs.get('tournament'):
            raise serializers.ValidationError({
                'tournament_id': 'This field is required.'
            })

        # Unique check: (tournament, match_number)
        tournament = attrs.get('tournament') or (
            self.instance.tournament if self.instance else None
        )
        match_number = attrs.get('match_number') or (
            self.instance.match_number if self.instance else None
        )

        if tournament and match_number:
            qs = Match.objects.filter(
                tournament=tournament,
                match_number=match_number,
            )
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError({
                    'match_number': (
                        f'Match #{match_number} already exists '
                        f'for this tournament.'
                    )
                })

        return attrs

    def create(self, validated_data):
        # Set created_by = request.user if available
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            validated_data.setdefault('created_by', request.user)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data.pop('tournament_id', None)
        return super().update(instance, validated_data)


class MatchParticipantSerializer(serializers.ModelSerializer):
    user_email_display = serializers.CharField(
        source='user.email', read_only=True
    )
    user_name_display = serializers.CharField(
        source='user.display_name', read_only=True
    )

    class Meta:
        model = MatchParticipant
        fields = [
            'id', 'match', 'user',
            'user_email', 'user_email_display',
            'user_mobile', 'user_upi_id',
            'user_ff_uid', 'user_ff_name',
            'user_name_display',
            'status', 'room_access_granted',
            'approved_by', 'approved_at', 'rejection_reason',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']