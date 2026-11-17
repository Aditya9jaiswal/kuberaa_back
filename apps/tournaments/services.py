# apps/tournaments/services.py
from django.db import transaction


class TournamentService:

    @staticmethod
    @transaction.atomic
    def register_user_for_tournament(
        tournament_id,
        user,
        free_fire_uid,
        free_fire_name,
        user_upi_id='',
        user_mobile='',
        referral_code=None,
        use_free_entry=False,
    ):
        from apps.tournaments.models import Tournament, Registration

        try:
            tournament = Tournament.objects.get(id=tournament_id)
        except Tournament.DoesNotExist:
            raise Exception('Tournament not found')

        if Registration.objects.filter(
            tournament=tournament, user=user
        ).exists():
            raise Exception('Already registered')

        if tournament.is_full:
            raise Exception('Tournament full')

        if not tournament.is_registration_open:
            raise Exception('Registration is closed')

        # ✅ FREE ENTRY FLOW
        if use_free_entry:
            from apps.users.services.referral_service import ReferralService
            ReferralService.validate_and_use_free_entry(user, tournament)

            reg = Registration.objects.create(
                tournament=tournament,
                user=user,
                free_fire_uid=free_fire_uid,
                free_fire_name=free_fire_name,
                user_upi_id=user_upi_id,
                user_mobile=user_mobile,
                status=Registration.Status.CONFIRMED,
                can_play=True,
            )

            Tournament.objects.filter(pk=tournament.pk).update(
                current_participants=tournament.registrations.count()
            )

            try:
                from apps.notifications.services import NotificationService
                NotificationService.create_notification(
                    user=user,
                    title="🎁 Free Entry Applied!",
                    message=f"Aapne {tournament.title} mein FREE entry use ki.",
                    notification_type='free_entry_used',
                )
            except Exception as e:
                print(f"⚠️ Notification failed: {e}")

            return reg

        # ✅ NORMAL PAYMENT FLOW
        reg = Registration.objects.create(
            tournament=tournament,
            user=user,
            free_fire_uid=free_fire_uid,
            free_fire_name=free_fire_name,
            user_upi_id=user_upi_id,
            user_mobile=user_mobile,
            status=Registration.Status.PENDING_PAYMENT,
            can_play=False,
        )

        Tournament.objects.filter(pk=tournament.pk).update(
            current_participants=tournament.registrations.count()
        )

        return reg