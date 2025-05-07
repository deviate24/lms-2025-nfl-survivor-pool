from django.contrib import admin
from .models import Team, Week, Pool, Entry, Pick, AuditLog


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'city', 'abbreviation', 'conference', 'division')
    list_filter = ('conference', 'division')
    search_fields = ('name', 'city', 'abbreviation')


@admin.register(Week)
class WeekAdmin(admin.ModelAdmin):
    list_display = ('number', 'description', 'start_date', 'end_date', 'deadline', 'is_double', 'reset_pool')
    list_filter = ('is_regular_season', 'is_double', 'reset_pool')
    search_fields = ('number', 'description')


@admin.register(Pool)
class PoolAdmin(admin.ModelAdmin):
    list_display = ('name', 'year', 'created_by', 'created_at', 'is_active')
    list_filter = ('year', 'is_active')
    search_fields = ('name', 'description')


@admin.register(Entry)
class EntryAdmin(admin.ModelAdmin):
    list_display = ('entry_name', 'pool', 'user', 'is_alive', 'eliminated_in_week')
    list_filter = ('pool', 'is_alive')
    search_fields = ('entry_name', 'user__username', 'user__email')


@admin.register(Pick)
class PickAdmin(admin.ModelAdmin):
    list_display = ('entry', 'week', 'team', 'result', 'created_at')
    list_filter = ('week', 'result')
    search_fields = ('entry__entry_name', 'team__name')
    
    def save_model(self, request, obj, form, change):
        """
        Override save_model to create an audit log entry when an admin
        creates or modifies a pick.
        """
        is_new = obj.pk is None
        super().save_model(request, obj, form, change)
        
        # Create audit log entry
        action = 'created' if is_new else 'modified'
        AuditLog.create(
            user=request.user,
            action=f"Admin {action} pick",
            entry=obj.entry,
            week=obj.week,
            details=f"Set {obj.entry.entry_name}'s Week {obj.week.number} pick to {obj.team} with result {obj.result}"
        )


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'user', 'action', 'entry', 'week')
    list_filter = ('timestamp', 'user', 'week')
    search_fields = ('action', 'details', 'user__username')
    readonly_fields = ('timestamp', 'user', 'action', 'entry', 'week', 'details')
    
    def has_add_permission(self, request):
        """Prevent manual creation of audit logs"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Prevent editing of audit logs"""
        return False
