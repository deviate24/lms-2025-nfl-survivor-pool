from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
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
    start_date = models.DateField()  # First day of the week
    end_date = models.DateField()  # Last day of the week
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
        """Check if this is the current week based on today's date"""
        today = timezone.now().date()
        return self.start_date <= today <= self.end_date
    
    def is_past_deadline(self):
        """Check if the pick deadline has passed"""
        return timezone.now() > self.deadline
    
    def is_future(self):
        """Check if this week is in the future"""
        return self.start_date > timezone.now().date()


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
        today = timezone.now().date()
        return Week.objects.filter(start_date__lte=today, end_date__gte=today).first()
    
    def get_alive_entries_count(self):
        """Get the count of entries still alive in this pool"""
        return self.entries.filter(is_alive=True).count()


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
        used_teams = self.get_used_teams()
        
        # If we're in playoffs and there's a reset, all teams are available
        if week and week.reset_pool:
            return Team.objects.all()
            
        return Team.objects.exclude(id__in=used_teams.values_list('id', flat=True))
    
    def eliminate(self, week):
        """Mark this entry as eliminated in the given week"""
        self.is_alive = False
        self.eliminated_in_week = week
        self.save()


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
    
    def clean(self):
        """Validate pick rules"""
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
        
        # Now we can safely check rules
        if self.week.is_past_deadline():
            raise ValidationError("Cannot make or change picks after the deadline")
        
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
        self.clean()
        super().save(*args, **kwargs)
        # Signal will handle sending confirmation email


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
        with transaction.atomic():
            # Find all picks for this team and week
            picks = Pick.objects.filter(team=self.team, week=self.week)
            
            # Update each pick's result
            for pick in picks:
                pick.result = self.result
                pick.save(update_fields=['result'])
                
                # If this is a loss, eliminate the entry
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
