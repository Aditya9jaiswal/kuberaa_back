from django.contrib import admin
from .models import Tournament, Registration


@admin.register(Tournament)
class TournamentAdmin(admin.ModelAdmin):
    list_display = (
        'display_id',
        'title',
        'tournament_type',   # ✅ ADD
        'status',
        'tournament_date',
        'current_participants',
        'maximum_participants',
        'entry_fee',
        'created_at',
    )
    list_filter = ('status', 'tournament_type', 'tournament_date')  # ✅ ADD
    search_fields = ('title', 'description', 'serial_number')
    ordering = ('-serial_number',)
    date_hierarchy = 'tournament_date'

    fieldsets = (
        ('Basic Info', {
            'fields': ('title', 'description', 'rules', 'prize_info')
        }),
        # ✅ YEH SECTION ADD KARO
        ('Game Type', {
            'fields': ('tournament_type',),
            'description': 'Game select karo — app mein is type ki image dikhegi'
        }),
        ('Schedule', {
            'fields': (
                'tournament_date',
                'start_time',
                'registration_start',
                'registration_end',
            )
        }),
        ('Capacity', {
            'fields': ('maximum_participants', 'current_participants')
        }),
        ('Payment / UPI', {
            'fields': ('entry_fee', 'upi_id', 'upi_name')
        }),
        ('Status', {
            'fields': ('status', 'created_by')
        }),
    )

    readonly_fields = (
        'serial_number',
        'current_participants',
        'created_at',
        'updated_at',
    )

    def display_id(self, obj):
        return obj.display_id
    display_id.short_description = 'ID'


@admin.register(Registration)
class RegistrationAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'tournament',
        'free_fire_uid',
        'free_fire_name',
        'status',
        'created_at',
    )
    list_filter = ('status', 'tournament')
    search_fields = ('user__email', 'free_fire_uid', 'free_fire_name')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')