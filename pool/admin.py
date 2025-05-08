from django.contrib import admin
from django.utils.html import format_html
from django.contrib import messages
from django.template.response import TemplateResponse
from django.shortcuts import redirect
from django.urls import path
from .models import Team, Week, Pool, Entry, Pick, AuditLog, PoolWeekSettings, WeeklyResult


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'city', 'abbreviation', 'conference', 'division')
    list_filter = ('conference', 'division')
    search_fields = ('name', 'city', 'abbreviation')


@admin.register(Week)
class WeekAdmin(admin.ModelAdmin):
    list_display = ('number', 'description', 'start_date', 'end_date', 'deadline', 'reset_pool', 'process_results_link')
    list_filter = ('is_regular_season', 'reset_pool')
    search_fields = ('number', 'description')
    
    def process_results_link(self, obj):
        return format_html(
            '<a href="{}" class="button">Set Results</a>',
            f'/admin/pool/week/{obj.id}/process-results/'
        )
    process_results_link.short_description = 'Game Results'
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<path:object_id>/process-results/', self.admin_site.admin_view(self.process_results_view), name='pool_week_process_results'),
        ]
        return custom_urls + urls
    
    def process_results_view(self, request, object_id):
        week_id = object_id
        week = Week.objects.get(id=week_id)
        teams = Team.objects.all().order_by('conference', 'division', 'city')
        
        # Process form submission
        if request.method == 'POST':
            action = request.POST.get('action', 'save')
            
            # Handle reset action
            if action == 'reset':
                # Delete all WeeklyResult objects for this week
                deleted_count, _ = WeeklyResult.objects.filter(week=week).delete()
                messages.success(request, f'Successfully reset all results for Week {week.number}. Removed {deleted_count} result records.')
                return redirect('admin:pool_week_process_results', object_id=week_id)
            
            # Handle save action (default)
            # Get selected teams and their results
            processed_teams = 0
            
            for team in teams:
                result_key = f'result_{team.id}'
                if result_key in request.POST and request.POST[result_key]:
                    result = request.POST[result_key]
                    notes = request.POST.get(f'notes_{team.id}', '')
                    
                    # Save or update the result
                    weekly_result, created = WeeklyResult.objects.update_or_create(
                        week=week,
                        team=team,
                        defaults={'result': result, 'notes': notes}
                    )
                    
                    processed_teams += 1
            
            messages.success(request, f'Successfully processed results for {processed_teams} teams in Week {week.number}')
            return redirect('admin:pool_week_changelist')
        
        # Prepare team data for the template
        team_data = []
        for team in teams:
            # Get existing result for this team if any
            result_obj = WeeklyResult.objects.filter(week=week, team=team).first()
            result = result_obj.result if result_obj else ''
            notes = result_obj.notes if result_obj else ''
            
            # Get pick count for this team
            pick_count = Pick.objects.filter(week=week, team=team).count()
            
            team_data.append({
                'team': team,
                'result': result,
                'notes': notes,
                'pick_count': pick_count,
                'has_picks': pick_count > 0
            })
        
        # Group teams by conference
        afc_teams = [t for t in team_data if t['team'].conference == 'AFC']
        nfc_teams = [t for t in team_data if t['team'].conference == 'NFC']
        
        context = {
            'title': f'Process Results for Week {week.number}',
            'opts': self.model._meta,
            'week': week,
            'afc_teams': afc_teams,
            'nfc_teams': nfc_teams,
            'has_permission': True,
        }
        
        return TemplateResponse(request, 'admin/pool/process_results.html', context)


class PoolWeekSettingsInline(admin.TabularInline):
    model = PoolWeekSettings
    extra = 0
    max_num = 0  # Don't allow adding new ones manually

@admin.register(Pool)
class PoolAdmin(admin.ModelAdmin):
    list_display = ('name', 'year', 'created_by', 'created_at', 'is_active', 'view_pool_links')
    list_filter = ('year', 'is_active')
    search_fields = ('name', 'description')
    inlines = [PoolWeekSettingsInline]
    
    def view_pool_links(self, obj):
        """
        Add links to view the pool detail and standings pages
        """
        return format_html(
            '<a href="{}" class="button" target="_blank" style="margin-right: 5px;">View Pool</a>'
            '<a href="{}" class="button" target="_blank">View Standings</a>',
            f'/pool/pool/{obj.id}/',
            f'/pool/pool/{obj.id}/standings/'
        )
    view_pool_links.short_description = 'View Pool'
    
    def save_model(self, request, obj, form, change):
        is_new = not obj.pk
        super().save_model(request, obj, form, change)
        
        if is_new:
            # Only create settings for a new pool
            weeks = Week.objects.all()
            for week in weeks:
                PoolWeekSettings.objects.create(
                    pool=obj,
                    week=week,
                    is_double=False
                )


class PickInline(admin.TabularInline):
    model = Pick
    extra = 1
    fields = ('week', 'team', 'result')

@admin.register(Entry)
class EntryAdmin(admin.ModelAdmin):
    list_display = ('entry_name', 'pool', 'user', 'is_alive', 'eliminated_in_week')
    list_filter = ('pool', 'is_alive')
    search_fields = ('entry_name', 'user__username', 'user__email')
    inlines = [PickInline]
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('add-multiple/', self.admin_site.admin_view(self.add_multiple_view), name='pool_entry_add_multiple'),
        ]
        return custom_urls + urls
    
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['show_add_multiple'] = True
        return super().changelist_view(request, extra_context)
    
    def add_multiple_view(self, request):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        if request.method == 'POST':
            pool_id = request.POST.get('pool')
            user_id = request.POST.get('user')
            count = int(request.POST.get('count', 1))
            
            # Validate input
            if not pool_id or not user_id or count < 1 or count > 20:
                messages.error(request, 'Invalid input parameters.')
                return redirect('admin:pool_entry_add_multiple')
            
            try:
                pool = Pool.objects.get(id=pool_id)
                user = User.objects.get(id=user_id)
            except (Pool.DoesNotExist, User.DoesNotExist):
                messages.error(request, 'Invalid pool or user selected.')
                return redirect('admin:pool_entry_add_multiple')
            
            # Find the highest entry number for this user in this pool
            username = user.username
            existing_entries = Entry.objects.filter(
                pool=pool,
                user=user,
                entry_name__startswith=f"{username} "
            )
            
            # Initialize the next entry number to 1
            next_entry_num = 1
            
            # Extract all existing entry numbers for this user in this pool
            existing_numbers = []
            for entry in existing_entries:
                try:
                    # Extract the number part from the entry name
                    entry_parts = entry.entry_name.split()
                    if len(entry_parts) > 1 and entry_parts[0] == username:
                        num = int(entry_parts[1])
                        existing_numbers.append(num)
                except (ValueError, IndexError):
                    continue
            
            # If we found existing numbered entries, find the max and add 1
            if existing_numbers:
                next_entry_num = max(existing_numbers) + 1
            
            # Create the new entries
            entries_created = 0
            for i in range(count):
                entry_name = f"{username} {next_entry_num + i}"
                Entry.objects.create(
                    pool=pool,
                    user=user,
                    entry_name=entry_name,
                    is_alive=True
                )
                entries_created += 1
            
            messages.success(request, f'Successfully created {entries_created} entries for {username} in {pool.name}.')
            return redirect('admin:pool_entry_changelist')
        
        # Prepare the form with pools and users
        context = {
            'title': 'Add Multiple Entries',
            'pools': Pool.objects.all().order_by('name'),
            'users': User.objects.all().order_by('username'),
            'has_permission': True,
            'opts': self.model._meta,
        }
        
        return TemplateResponse(request, 'admin/pool/entry/add_multiple.html', context)


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
    list_display = ('timestamp', 'user', 'action', 'entry_link', 'pool_link', 'week', 'details')
    list_filter = ('action', 'timestamp', 'week', ('entry__pool', admin.RelatedOnlyFieldListFilter))
    search_fields = ('user__username', 'entry__entry_name', 'entry__pool__name', 'details', 'action')
    readonly_fields = ('timestamp', 'user', 'action', 'entry', 'week', 'details')
    date_hierarchy = 'timestamp'
    ordering = ('-timestamp',)
    
    def entry_link(self, obj):
        if obj.entry:
            return format_html('<a href="{0}">{1}</a>', 
                               f'/admin/pool/entry/{obj.entry.id}/change/', 
                               obj.entry.entry_name)
        return '-'
    entry_link.short_description = 'Entry'
    entry_link.admin_order_field = 'entry__entry_name'
    
    def pool_link(self, obj):
        if obj.entry and obj.entry.pool:
            return format_html('<a href="{0}">{1}</a>', 
                               f'/admin/pool/pool/{obj.entry.pool.id}/change/', 
                               obj.entry.pool.name)
        return '-'
    pool_link.short_description = 'Pool'
    pool_link.admin_order_field = 'entry__pool__name'
    
    def has_add_permission(self, request):
        """Prevent manual creation of audit logs"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Prevent editing of audit logs"""
        return False


@admin.register(WeeklyResult)
class WeeklyResultAdmin(admin.ModelAdmin):
    list_display = ('week', 'team', 'result', 'notes', 'pick_count')
    list_filter = ('week', 'result')
    search_fields = ('team__name', 'team__city', 'notes')
    
    def pick_count(self, obj):
        count = Pick.objects.filter(week=obj.week, team=obj.team).count()
        return format_html('<a href="{}?team__id__exact={}&week__id__exact={}">{} picks</a>', 
                          '/admin/pool/pick/', obj.team.id, obj.week.id, count)
    pick_count.short_description = 'Picks'
