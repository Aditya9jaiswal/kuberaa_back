# apps/results/serializers.py
from rest_framework import serializers
from .models import Result

class ResultSerializer(serializers.ModelSerializer):
    user_email = serializers.SerializerMethodField()
    user_name = serializers.SerializerMethodField()
    user_mobile = serializers.SerializerMethodField()
    match_title = serializers.SerializerMethodField()
    tournament_title = serializers.SerializerMethodField()
    screenshot_url = serializers.SerializerMethodField()
    payout_status = serializers.SerializerMethodField()

    class Meta:
        model = Result
        fields = [
            'id', 'match', 'user', 'user_email', 'user_name', 'user_mobile',
            'match_title', 'tournament_title', 'free_fire_uid', 'player_name',
            'kills', 'placement', 'score', 'points_earned',
            'prize_amount', 'per_kill_prize', 'entry_fee',
            'is_paid', 'paid_at', 'payout_status',
            'screenshot', 'screenshot_url', 'ocr_confidence',
            'verification_status', 'published_at', 'created_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_user_email(self, obj):
        return obj.user.email if obj.user else None

    def get_user_name(self, obj):
        if obj.user: return getattr(obj.user, 'display_name', '') or obj.user.email
        return obj.player_name

    def get_user_mobile(self, obj):
        return getattr(obj.user, 'mobile_number', '') if obj.user else None

    def get_match_title(self, obj):
        return obj.match.title if obj.match else "Unknown Match"

    def get_tournament_title(self, obj):
        if obj.match and obj.match.tournament: return obj.match.tournament.title
        return "Unknown Tournament"

    def get_screenshot_url(self, obj):
        if obj.screenshot:
            request = self.context.get('request')
            if request: return request.build_absolute_uri(obj.screenshot.url)
            return obj.screenshot.url
        return None

    def get_payout_status(self, obj):
        return "PAID" if obj.is_paid else "PENDING"