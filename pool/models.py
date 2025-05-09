from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.admin.options import ModelAdmin
from django.db.models import UniqueConstraint


class Team(models.Model):
    """
    Represents an NFL team that can be picked in the survivor pool.
    """
    name = models.CharField(max_length=100)  # Full team name (e.g., "Kansas City Chiefs")
    city = models.CharField(max_length=100)  # Team city (e.g., "Kansas City")
    abbreviation = models.CharField(max_length=5)  # Short code (e.g., "KC")
    conference = models.CharField(max_length=3, choices=[('AFC', 'AFC'), ('NFC', 'NFC')])
    division = models.CharField(max_length=10, choices=[
        ('East', 'East'),
        ('West', 'West'),
        ('North', 'North'),
        ('South', 'South'),
    ])
    logo_url = models.URLField(blank=True, null=True)  # URL to team logo image
    
    class Meta:
        ordering = ['city', 'name']
    
    def __str__(self):
        return f"{self.city} {self.name}"


class Week(models.Model):
    """
    Represents a week in the NFL season.
    Each week has a start and end date, and a deadline for picks.
    """
    number = models.PositiveIntegerField()  # Week number (1-18 for regular season)
    description = models.CharField(max_length=100, blank=True)  # Optional description
    start_date = models.DateTimeField()  # First day of the week with time
    end_date = models.DateTimeField()  # Last day of the week with time
    deadline = models.DateTimeField()  # Deadline for picks (Thursday 4PM PT)
    is_regular_season = models.BooleanField(default=True)  # Regular season or playoffs
    # is_double moved to PoolWeekSettings
    reset_pool = models.BooleanField(default=False)  # Whether to reset used teams (for playoffs)
    reminder_time = models.DateTimeField(null=True, blank=True)  # When to send reminders
    email_sent = models.BooleanField(default=False)  # Whether pick report emails have been sent
    
    class Meta:
        ordering = ['number']
    
    def __str__(self):
        return f"Week {self.number}" + (f" ({self.description})" if self.description else "")
    
    def is_current(self):
        """Check if this is the current week based on current date and time"""
        now = timezone.now()
        return self.start_date <= now <= self.end_date
    
    def is_past_deadline(self, for_admin=False):
        """Check if the pick deadline has passed"""
        # If this is for admin use, pretend the deadline hasn't passed
        if for_admin:
            return False
            
        # Normal deadline check
        return timezone.now() > self.deadline
    
    def is_future(self):
        """Check if this week is in the future"""
        return self.start_date > timezone.now()


class PoolWeekSettings(models.Model):
    """
    Represents pool-specific settings for each week.
    This allows customizing which weeks are double-pick weeks per pool.
    """
    pool = models.ForeignKey('Pool', on_delete=models.CASCADE, related_name='week_settings')
    week = models.ForeignKey('Week', on_delete=models.CASCADE, related_name='pool_settings')
    is_double = models.BooleanField(default=False)  # Whether this is a double-pick week for this pool
    
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['pool', 'week'],
                name='unique_week_settings_per_pool'
            )
        ]
    
    def __str__(self):
        return f"{self.pool.name} - Week {self.week.number} Settings"


class Pool(models.Model):
    """
    Represents a survivor pool contest.
    """
    name = models.CharField(max_length=100)  # Name of the pool
    year = models.PositiveIntegerField()  # Season year
    description = models.TextField(blank=True)  # Optional description
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)  # Whether the pool is active
    weeks = models.ManyToManyField('Week', through='PoolWeekSettings', related_name='pools')
    
    def __str__(self):
        return f"{self.name} ({self.year})"
    
    def get_current_week(self):
        """Get the current week for this pool"""
        now = timezone.now()
        return Week.objects.filter(start_date__lte=now, end_date__gte=now).first()
    
    def get_alive_entries_count(self):
        """Get the count of entries still alive in this pool"""
        return self.entries.filter(is_alive=True).count()
    
    def process_missing_picks_eliminations(self):
        """Automatically eliminate entries that didn't make a pick by the deadline"""
        now = timezone.now()
        
        # Find weeks where deadline has passed but we're still within the week's timeframe
        active_weeks = Week.objects.filter(
            deadline__lt=now,
            end_date__gte=now
        )
        
        eliminated_count = 0
        
        for week in active_weeks:
            # Get alive entries for this pool
            alive_entries = self.entries.filter(is_alive=True)
            
            for entry in alive_entries:
                # Check if this entry has a pick for this week
                has_pick = Pick.objects.filter(entry=entry, week=week).exists()
                
                if not has_pick:
                    # No pick was made before deadline - eliminate the entry
                    entry.is_alive = False
                    entry.eliminated_in_week = week
                    entry.save()
                    
                    # Log the elimination
                    AuditLog.create(
                        user=None,
                        action="Auto-Eliminated",
                        entry=entry,
                        week=week,
                        details="Automatically eliminated due to no pick by deadline"
                    )
                    
                    eliminated_count += 1
        
        return eliminated_count


class Entry(models.Model):
    """
    Represents a user's entry in a pool.
    A user can have multiple entries in the same pool.
    """
    pool = models.ForeignKey(Pool, on_delete=models.CASCADE, related_name='entries')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='entries')
    entry_name = models.CharField(max_length=100)  # Name of the entry (e.g., "username-1")
    created_at = models.DateTimeField(auto_now_add=True)
    is_alive = models.BooleanField(default=True)  # Whether the entry is still alive
    eliminated_in_week = models.ForeignKey(
        Week, on_delete=models.SET_NULL, null=True, blank=True, related_name='eliminated_entries'
    )
    
    class Meta:
        verbose_name_plural = 'Entries'
        constraints = [
            # Ensure entry_name is unique per pool
            UniqueConstraint(fields=['pool', 'entry_name'], name='unique_entry_name_per_pool')
        ]
    
    def __str__(self):
        return f"{self.entry_name} ({self.pool})"
    
    def get_used_teams(self):
        """Get all teams this entry has already picked"""
        return Team.objects.filter(picks__entry=self).distinct()
    
    def get_available_teams(self, week=None):
        """Get teams that are still available to pick"""
        # If we're in playoffs and there's a reset, all teams are available
        if week and week.reset_pool:
            return Team.objects.all()
        
        # Get teams used in all weeks
        used_teams = self.get_used_teams()
        
        # Special case: If current week deadline hasn't passed yet, don't exclude the
        # team(s) picked for the current week. This way, other users can't deduce 
        # what team has been picked by seeing what's missing from the available list
        if week and not week.is_past_deadline():
            # Get IDs of teams used in previous weeks only
            used_team_ids = Pick.objects.filter(
                entry=self,
                week__number__lt=week.number  # Only earlier weeks
            ).values_list('team__id', flat=True).distinct()
            
            # Return all teams except those used in previous weeks
            return Team.objects.exclude(id__in=used_team_ids)
            
        # Otherwise (after deadline or no specific week), exclude all used teams
        return Team.objects.exclude(id__in=used_teams.values_list('id', flat=True))
    
    def eliminate(self, week):
        """Mark this entry as eliminated in the given week"""
        self.is_alive = False
        self.eliminated_in_week = week
        self.save()
        
    def get_last_pick_for_week(self, week):
        """Get the last pick for a specific week"""
        return self.picks.filter(week=week).last()
        
    def get_last_pick_in_elimination_week(self):
        """Get the last pick for the week this entry was eliminated in"""
        if not self.eliminated_in_week:
            return None
        return self.picks.filter(week=self.eliminated_in_week).last()
        
    def get_all_picks_in_elimination_week(self):
        """Get all picks for the week this entry was eliminated in"""
        if not self.eliminated_in_week:
            return []
        return self.picks.filter(week=self.eliminated_in_week).all()


class Pick(models.Model):
    """
    Represents a user's pick of a team for a specific week.
    """
    entry = models.ForeignKey(Entry, on_delete=models.CASCADE, related_name='picks')
    week = models.ForeignKey(Week, on_delete=models.CASCADE, related_name='picks')
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='picks')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    result = models.CharField(
        max_length=10,
        choices=[
            ('pending', 'Pending'),
            ('win', 'Win'),
            ('loss', 'Loss'),
            ('tie', 'Tie'),  # Ties count as losses
        ],
        default='pending'
    )
    
    class Meta:
        # No rank field needed - we'll store two rows for double-pick weeks
        constraints = [
            # Ensure a user can only have one pick per team per week
            models.UniqueConstraint(
                fields=['entry', 'week', 'team'],
                name='unique_team_per_entry_per_week'
            ),
        ]
    
    def __str__(self):
        return f"{self.entry.entry_name} picked {self.team} for {self.week}"
    
    def clean(self, *args, **kwargs):
        """Validate pick rules"""
        # Check if this is a superadmin request (from admin interface)   
        is_superadmin = kwargs.pop('is_superadmin', False)
        
        # Check if we're in the admin interface (direct from request or through stack inspection)
        admin_request = kwargs.pop('admin_request', False)
        
        # This is a more robust way to detect admin usage
        if not admin_request:
            import inspect
            admin_frames = [frame for frame in inspect.stack() 
                           if '/admin/' in frame.filename if hasattr(frame, 'filename')]
            admin_request = len(admin_frames) > 0
        
        # First, let's handle the week
        if not hasattr(self, 'week') or not self.week:
            # Get current week
            today = timezone.now().date()
            current_week = self._meta.model.week.field.related_model.objects.filter(
                start_date__lte=today,
                end_date__gte=today
            ).first()
            
            # If no current week, get the next upcoming week
            if not current_week:
                current_week = self._meta.model.week.field.related_model.objects.filter(
                    start_date__gt=today
                ).order_by('start_date').first()
            
            # If still no week, fallback to the first week
            if not current_week:
                current_week = self._meta.model.week.field.related_model.objects.order_by('number').first()
                
            if current_week:
                self.week = current_week
            else:
                raise ValidationError("Week is required and no valid weeks found in the system")
            
        if not hasattr(self, 'entry') or not self.entry:
            # For clean method, we must have an entry
            # Just set a default error that the form will override with its own validation
            raise ValidationError("Entry is required")
            
        if not hasattr(self, 'team') or not self.team:
            raise ValidationError("Team is required")
        
        # Superadmins and admin requests bypass deadline and elimination checks
        if not (is_superadmin or admin_request):
            # Only regular users are restricted by deadline
            if self.week.is_past_deadline():
                raise ValidationError("Cannot make or change picks after the deadline")
            
            # Only regular users are restricted by elimination status
            if not self.entry.is_alive:
                raise ValidationError("This entry has been eliminated and cannot make picks")
        
        # Get the pool-specific settings for this week
        week_settings = PoolWeekSettings.objects.filter(pool=self.entry.pool, week=self.week).first()
        if not week_settings:
            raise ValidationError("Week settings not found for this pool")
        
        # Check if team was already used by this entry (unless reset_pool)
        if not self.week.reset_pool:
            used_teams = self.entry.get_used_teams()
            if self.team in used_teams and not self.pk:  # Allow editing existing pick
                raise ValidationError(f"You have already used {self.team} in a previous week")
        
        # Check if this is a double-pick week
        if week_settings.is_double:
            # Count existing picks for this week
            existing_picks = Pick.objects.filter(entry=self.entry, week=self.week)
            if self.pk:  # If editing, exclude current pick
                existing_picks = existing_picks.exclude(pk=self.pk)
            
            if existing_picks.count() >= 2:
                raise ValidationError("You have already made both picks for this double-pick week")
        else:
            # For single-pick weeks, we handle managing picks in the view
            # We'll allow changing picks before the deadline but ensure there's only one active pick
            # This validation step is no longer needed as we delete any existing picks when saving a new one
            pass
    
    def save(self, *args, **kwargs):
        # Check if this is a superadmin or admin save
        is_superadmin = kwargs.pop('is_superadmin', False)
        admin_request = kwargs.pop('admin_request', False)
        
        # Pass the flags to clean
        self.clean(is_superadmin=is_superadmin, admin_request=admin_request)
        
        # Save the model
        super().save(*args, **kwargs)
        
        # Signal will handle sending confirmation email for regular users
        # but not for admin actions


class WeeklyResult(models.Model):
    """
    Records the win/loss result for each team in a given week.
    This is set by admins after games are completed.
    """
    week = models.ForeignKey(Week, on_delete=models.CASCADE)
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    result = models.CharField(
        max_length=10,
        choices=[
            ('win', 'Win'),
            ('loss', 'Loss'),
            ('tie', 'Tie'),  # For NFL games that end in a tie
        ]
    )
    notes = models.TextField(blank=True, help_text="Optional notes about the game/result")
    
    class Meta:
        ordering = ['week', 'team__city']
        constraints = [
            models.UniqueConstraint(
                fields=['week', 'team'],
                name='unique_team_result_per_week'
            ),
        ]
    
    def __str__(self):
        return f"{self.team} - {self.get_result_display()} (Week {self.week.number})"
    
    def save(self, *args, **kwargs):
        # Save the result
        super().save(*args, **kwargs)
        
        # Update all picks for this team and week
        from django.db import transaction
        from django.db.models import Count, Q
        
        with transaction.atomic():
            # Find all picks for this team and week
            picks = Pick.objects.filter(team=self.team, week=self.week)
            
            # Update each pick's result
            for pick in picks:
                pick.result = self.result
                # Pass admin_request flag to bypass deadline validation
                pick.save(update_fields=['result'], admin_request=True)
                
                # Get the pool settings to check if this is a double-pick week
                pool = pick.entry.pool
                week_settings = PoolWeekSettings.objects.filter(
                    pool=pool,
                    week=self.week
                ).first()
                
                is_double_pick = week_settings and week_settings.is_double
                
                if is_double_pick:
                    # For double-pick weeks, we need special handling
                    # Only process eliminations if both picks have results
                    entry_picks = Pick.objects.filter(entry=pick.entry, week=self.week)
                    
                    # Skip if we don't have both picks with results yet
                    if entry_picks.count() < 2 or entry_picks.filter(result='pending').exists():
                        continue
                    
                    # Count wins for this entry
                    win_count = entry_picks.filter(result='win').count()
                    
                    # In double-pick weeks, you need BOTH picks to win (win_count=2)
                    # Any entry with 0 or 1 wins gets eliminated
                    if win_count < 2:
                        # If either pick lost or tied, eliminate immediately
                        if pick.entry.is_alive:
                            pick.entry.is_alive = False
                            pick.entry.eliminated_in_week = self.week
                            pick.entry.save(update_fields=['is_alive', 'eliminated_in_week'])
                            
                            # Log the elimination
                            AuditLog.create(
                                user=None,  # System action
                                action="ENTRY_ELIMINATED",
                                entry=pick.entry,
                                week=self.week,
                                details=f"{pick.entry.entry_name} was eliminated in Week {self.week.number} - only had {win_count} win(s) in double-pick week"
                            )
                else:
                    # Normal elimination for single-pick weeks
                    if self.result == 'loss' or self.result == 'tie':
                        entry = pick.entry
                        if entry.is_alive:
                            entry.is_alive = False
                            entry.eliminated_in_week = self.week
                            entry.save(update_fields=['is_alive', 'eliminated_in_week'])
                            
                            # Log the elimination
                            AuditLog.create(
                                user=None,  # System action
                                action="ENTRY_ELIMINATED",
                                entry=entry,
                                week=self.week,
                                details=f"{entry.entry_name} was eliminated in Week {self.week.number} for picking {self.team}, which {self.get_result_display().lower()}"
                            )


class AuditLog(models.Model):
    """
    Logs administrative actions for transparency and auditing.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True)
    action = models.CharField(max_length=255)  # Description of the action
    timestamp = models.DateTimeField(auto_now_add=True)
    entry = models.ForeignKey(Entry, on_delete=models.CASCADE, null=True, blank=True)
    week = models.ForeignKey(Week, on_delete=models.CASCADE, null=True, blank=True)
    details = models.TextField(blank=True)  # Additional details about the action
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.timestamp}: {self.user or 'System'} - {self.action}"
    
    @classmethod
    def create(cls, user, action, entry=None, week=None, details=''):
        """Helper method to create an audit log entry"""
        return cls.objects.create(
            user=user,
            action=action,
            entry=entry,
            week=week,
            details=details
        )
