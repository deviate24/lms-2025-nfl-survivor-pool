from django.contrib import admin
from django.utils.html import format_html
from django.contrib import messages
from django.template.response import TemplateResponse
from django.shortcuts import redirect
from django.urls import path
from django import forms
from django.core.exceptions import ValidationError
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


# Custom form for PickInline to bypass deadline validation for superadmins
class PickAdminForm(forms.ModelForm):
    class Meta:
        model = Pick
        fields = ['week', 'team', 'result']
    
    def clean(self):
        cleaned_data = super().clean()
        # Check if the user is a superadmin (we'll add this flag in the PickInline)
        if not getattr(self, 'is_superadmin', False):
            # Regular user, enforce normal validation
            week = cleaned_data.get('week')
            if week and week.is_past_deadline():
                raise ValidationError("Cannot make or change picks after the deadline")
            
            entry = cleaned_data.get('entry')
            if entry and not entry.is_alive:
                raise ValidationError("This entry has been eliminated and cannot make picks")
        
        return cleaned_data

# Custom inline formset to bypass deadline validation for superadmins
class SuperadminPickInlineFormSet(forms.models.BaseInlineFormSet):
    def clean(self):
        # Only perform validation for non-superadmins
        if not getattr(self.request, 'user', None) or not self.request.user.is_superuser:
            super().clean()

class PickInline(admin.TabularInline):
    model = Pick
    extra = 1
    fields = ('week', 'team', 'result', 'created_at', 'direct_edit_link')
    readonly_fields = ('created_at', 'direct_edit_link')
    formset = SuperadminPickInlineFormSet
    
    def get_formset(self, request, obj=None, **kwargs):
        # Store the request in the formset for access in clean method
        formset = super().get_formset(request, obj, **kwargs)
        formset.request = request
        return formset
    
    def direct_edit_link(self, obj):
        """Provide a direct edit link for superadmins that bypasses all validation"""
        if obj.pk and hasattr(self, 'request') and self.request.user.is_superuser:
            return format_html(
                '<a href="{}" class="button" style="background-color: #d00; color: white;">Direct Edit</a>',
                f'/pool/admin/pick/{obj.pk}/edit/'
            )
        return ""
    direct_edit_link.short_description = "Admin Actions"
    
    def get_readonly_fields(self, request, obj=None):
        self.request = request  # Store request for use in direct_edit_link
        # Make all fields editable for superusers except created_at and the direct edit link
        if request.user.is_superuser:
            return ('created_at', 'direct_edit_link')
        # For non-superusers, make all fields read-only
        return ('week', 'team', 'result', 'created_at', 'direct_edit_link')

@admin.register(Entry)
class EntryAdmin(admin.ModelAdmin):
    list_display = ('entry_name', 'pool', 'user', 'is_alive', 'eliminated_in_week', 'entry_actions')
    list_filter = ('pool', 'is_alive')
    search_fields = ('entry_name', 'user__username', 'user__email')
    
    def save_formset(self, request, form, formset, change):
        """Handle inline Pick modifications with audit logging"""
        instances = formset.save(commit=False)
        
        # Track original pick data for comparison
        for form in formset.forms:
            if form.instance.pk and form.has_changed() and request.user.is_superuser:
                # Get the original Pick object from database
                original_obj = Pick.objects.get(pk=form.instance.pk)
                form.instance._original_team = original_obj.team
                form.instance._original_result = original_obj.result
        
        # For each instance, save with superadmin flag if user is superadmin
        for instance in instances:
            if isinstance(instance, Pick) and request.user.is_superuser:
                # Pass is_superadmin flag to bypass deadline restrictions
                instance.save(is_superadmin=True)
            else:
                instance.save()
        
        # Save many-to-many relationships
        formset.save_m2m()
        
        # Process audit logging and entry status updates for changed picks
        for instance in instances:
            if hasattr(instance, '_original_team') and hasattr(instance, '_original_result'):
                changes = []
                
                # Check if team changed
                if instance._original_team != instance.team:
                    changes.append(f"team from {instance._original_team} to {instance.team}")
                
                # Check if result changed
                if instance._original_result != instance.result:
                    changes.append(f"result from {instance._original_result} to {instance.result}")
                
                if changes:
                    changes_text = " and ".join(changes)
                    AuditLog.create(
                        user=request.user,
                        action="ADMIN_MODIFIED_PICK",
                        entry=instance.entry,
                        week=instance.week,
                        details=f"Administrator {request.user.username} updated pick {changes_text}."
                    )
                    
                    # If result changed from win to loss or vice versa, we might need to update entry status
                    if instance._original_result != instance.result and \
                       (instance._original_result == 'win' or instance.result == 'win') and \
                       (instance._original_result == 'loss' or instance.result == 'loss'):
                        # Get pool settings
                        pool_settings = PoolWeekSettings.objects.filter(
                            pool=instance.entry.pool, 
                            week=instance.week
                        ).first()
                        is_double_pick = pool_settings and pool_settings.is_double
                        
                        if is_double_pick:
                            # For double-pick weeks, we need to check all picks for this entry
                            all_picks = Pick.objects.filter(entry=instance.entry, week=instance.week)
                            
                            # Count how many are wins
                            win_count = all_picks.filter(result='win').count()
                            loss_count = all_picks.filter(result__in=['loss', 'tie']).count()
                            
                            # If two picks and both are losses, eliminate
                            if all_picks.count() == 2 and loss_count == 2 and instance.entry.is_alive:
                                instance.entry.is_alive = False
                                instance.entry.eliminated_in_week = instance.week
                                instance.entry.save(update_fields=['is_alive', 'eliminated_in_week'])
                                
                                AuditLog.create(
                                    user=request.user,
                                    action="ADMIN_PICK_CHANGE_ELIMINATED",
                                    entry=instance.entry,
                                    week=instance.week,
                                    details=f"Entry was eliminated due to admin changing pick result to loss/tie."
                                )
                            # If was eliminated but now has at least one win, potentially revive
                            elif win_count > 0 and not instance.entry.is_alive and instance.entry.eliminated_in_week == instance.week:
                                # Check if any entry has 2 wins for this week
                                entries_with_two_wins = Entry.objects.filter(
                                    pool=instance.entry.pool,
                                    picks__week=instance.week,
                                    picks__result='win'
                                ).annotate(win_count=models.Count('picks')).filter(win_count=2)
                                
                                # If no entries with two wins, or this entry has two wins, revive it
                                if not entries_with_two_wins.exists() or (win_count == 2):
                                    instance.entry.is_alive = True
                                    instance.entry.eliminated_in_week = None
                                    instance.entry.save(update_fields=['is_alive', 'eliminated_in_week'])
                                    
                                    AuditLog.create(
                                        user=request.user,
                                        action="ADMIN_PICK_CHANGE_REVIVED",
                                        entry=instance.entry,
                                        week=instance.week,
                                        details=f"Entry was revived due to admin changing pick result to win."
                                    )
                        else:
                            # For regular weeks, it's simpler
                            if instance.result in ['loss', 'tie'] and instance.entry.is_alive:
                                instance.entry.is_alive = False
                                instance.entry.eliminated_in_week = instance.week
                                instance.entry.save(update_fields=['is_alive', 'eliminated_in_week'])
                                
                                AuditLog.create(
                                    user=request.user,
                                    action="ADMIN_PICK_CHANGE_ELIMINATED",
                                    entry=instance.entry,
                                    week=instance.week,
                                    details=f"Entry was eliminated due to admin changing pick result to {instance.result}."
                                )
                            elif instance.result == 'win' and not instance.entry.is_alive and instance.entry.eliminated_in_week == instance.week:
                                instance.entry.is_alive = True
                                instance.entry.eliminated_in_week = None
                                instance.entry.save(update_fields=['is_alive', 'eliminated_in_week'])
                                
                                AuditLog.create(
                                    user=request.user,
                                    action="ADMIN_PICK_CHANGE_REVIVED",
                                    entry=instance.entry,
                                    week=instance.week,
                                    details=f"Entry was revived due to admin changing pick result to win."
                                )
    inlines = [PickInline]
    actions = ['mark_as_alive', 'mark_as_eliminated']
    
    def entry_actions(self, obj):
        if obj.is_alive:
            return format_html(
                '<a href="{}" class="button" style="background-color: #dc3545; color: white;">Mark Eliminated</a>',
                f'/admin/pool/entry/{obj.id}/mark-eliminated/'
            )
        else:
            return format_html(
                '<a href="{}" class="button" style="background-color: #28a745; color: white;">Mark Alive</a>',
                f'/admin/pool/entry/{obj.id}/mark-alive/'
            )
    entry_actions.short_description = 'Actions'
    
    def save_model(self, request, obj, form, change):
        # Track changes before saving
        is_new = not obj.pk
        
        if not is_new:
            # Get the original object from database for comparison
            original_obj = Entry.objects.get(pk=obj.pk)
            was_alive = original_obj.is_alive
            had_eliminated_week = original_obj.eliminated_in_week
        
        # Save the model
        super().save_model(request, obj, form, change)
        
        # Create audit log entries for status changes
        if not is_new and request.user.is_superuser:
            # Check if alive status changed
            if was_alive != obj.is_alive:
                action = "ADMIN_MARKED_ALIVE" if obj.is_alive else "ADMIN_MARKED_ELIMINATED"
                details = f"Administrator {request.user.username} changed entry status from {'Alive' if was_alive else 'Eliminated'} to {'Alive' if obj.is_alive else 'Eliminated'}"
                
                AuditLog.create(
                    user=request.user,
                    action=action,
                    entry=obj,
                    week=obj.eliminated_in_week,
                    details=details
                )
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('add-multiple/', self.admin_site.admin_view(self.add_multiple_view), name='pool_entry_add_multiple'),
            path('<path:object_id>/mark-alive/', self.admin_site.admin_view(self.mark_alive_view), name='pool_entry_mark_alive'),
            path('<path:object_id>/mark-eliminated/', self.admin_site.admin_view(self.mark_eliminated_view), name='pool_entry_mark_eliminated'),
        ]
        return custom_urls + urls
        
    def mark_alive_view(self, request, object_id):
        entry = self.get_object(request, object_id)
        if not entry:
            messages.error(request, "Entry not found.")
            return redirect('admin:pool_entry_changelist')
            
        if entry.is_alive:
            messages.info(request, f"Entry '{entry.entry_name}' is already marked as alive.")
        else:
            original_status = "Eliminated"
            original_week = entry.eliminated_in_week
            
            # Update entry status
            entry.is_alive = True
            entry.eliminated_in_week = None
            entry.save(update_fields=['is_alive', 'eliminated_in_week'])
            
            # Create audit log entry
            AuditLog.create(
                user=request.user,
                action="ADMIN_MARKED_ALIVE",
                entry=entry,
                week=original_week,
                details=f"Administrator {request.user.username} changed entry status from {original_status} to Alive"
            )
            
            messages.success(request, f"Entry '{entry.entry_name}' has been marked as alive.")
            
        return redirect('admin:pool_entry_change', object_id=object_id)
    
    def mark_eliminated_view(self, request, object_id):
        entry = self.get_object(request, object_id)
        if not entry:
            messages.error(request, "Entry not found.")
            return redirect('admin:pool_entry_changelist')
            
        if not entry.is_alive:
            messages.info(request, f"Entry '{entry.entry_name}' is already marked as eliminated.")
            return redirect('admin:pool_entry_change', object_id=object_id)
        
        # For marking as eliminated, we need to select a week
        if request.method == 'POST':
            week_id = request.POST.get('week')
            if not week_id:
                messages.error(request, "Please select a week when this entry was eliminated.")
                return redirect('admin:pool_entry_mark_eliminated', object_id=object_id)
                
            try:
                week = Week.objects.get(id=week_id)
            except Week.DoesNotExist:
                messages.error(request, "Selected week not found.")
                return redirect('admin:pool_entry_mark_eliminated', object_id=object_id)
                
            # Update entry status
            original_status = "Alive"
            entry.is_alive = False
            entry.eliminated_in_week = week
            entry.save(update_fields=['is_alive', 'eliminated_in_week'])
            
            # Create audit log entry
            AuditLog.create(
                user=request.user,
                action="ADMIN_MARKED_ELIMINATED",
                entry=entry,
                week=week,
                details=f"Administrator {request.user.username} changed entry status from {original_status} to Eliminated in Week {week.number}"
            )
            
            messages.success(request, f"Entry '{entry.entry_name}' has been marked as eliminated in Week {week.number}.")
            return redirect('admin:pool_entry_change', object_id=object_id)
        
        # Show a form to select the week
        weeks = Week.objects.all().order_by('number')
        return TemplateResponse(request, 'admin/pool/entry/mark_eliminated.html', {
            'entry': entry,
            'weeks': weeks,
            'opts': self.model._meta,
            'original': entry,
            'title': f"Mark '{entry.entry_name}' as Eliminated",
        })
    
    def mark_as_alive(self, modeladmin, request, queryset):
        # Bulk action to mark entries as alive
        count = 0
        for entry in queryset:
            if not entry.is_alive:
                original_week = entry.eliminated_in_week
                entry.is_alive = True
                entry.eliminated_in_week = None
                entry.save(update_fields=['is_alive', 'eliminated_in_week'])
                
                # Create audit log entry
                AuditLog.create(
                    user=request.user,
                    action="ADMIN_MARKED_ALIVE",
                    entry=entry,
                    week=original_week,
                    details=f"Administrator {request.user.username} marked entry as Alive (bulk action)"
                )
                count += 1
                
        if count:
            messages.success(request, f"{count} entries have been marked as alive.")
        else:
            messages.info(request, "No entries were updated. They might already be marked as alive.")
    mark_as_alive.short_description = "Mark selected entries as alive"
    
    def mark_as_eliminated(self, modeladmin, request, queryset):
        # We can only handle elimination in bulk if there is a current week
        current_week = Week.objects.filter(
            start_date__lte=timezone.now().date(),
            end_date__gte=timezone.now().date()
        ).first()
        
        if not current_week:
            messages.error(request, "Can't determine the current week. Please use individual actions to mark entries as eliminated.")
            return
            
        count = 0
        for entry in queryset:
            if entry.is_alive:
                entry.is_alive = False
                entry.eliminated_in_week = current_week
                entry.save(update_fields=['is_alive', 'eliminated_in_week'])
                
                # Create audit log entry
                AuditLog.create(
                    user=request.user,
                    action="ADMIN_MARKED_ELIMINATED",
                    entry=entry,
                    week=current_week,
                    details=f"Administrator {request.user.username} marked entry as Eliminated in Week {current_week.number} (bulk action)"
                )
                count += 1
                
        if count:
            messages.success(request, f"{count} entries have been marked as eliminated in Week {current_week.number}.")
        else:
            messages.info(request, "No entries were updated. They might already be marked as eliminated.")
    mark_as_eliminated.short_description = "Mark selected entries as eliminated (current week)"
    
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
    list_display = ('timestamp', 'pool_link', 'user', 'entry_link', 'week', 'action', 'details')
    list_filter = ('action', 'timestamp', 'week', ('entry__pool', admin.RelatedOnlyFieldListFilter))
    search_fields = ('user__username', 'entry__entry_name', 'entry__pool__name', 'details', 'action')
    readonly_fields = ('timestamp', 'user', 'action', 'entry', 'week', 'details')
    date_hierarchy = 'timestamp'
    ordering = ('-timestamp',)
    list_per_page = 50  # Show 50 logs per page by default
    list_max_show_all = 500  # Allow showing up to 500 logs on one page
    
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


# We'll enhance the PickInline class instead of creating a separate PickAdmin
