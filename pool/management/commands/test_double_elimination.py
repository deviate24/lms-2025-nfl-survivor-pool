from django.core.management.base import BaseCommand
from pool.models import Week, Team, Entry, Pool, Pick, WeeklyResult, PoolWeekSettings
from django.utils import timezone
from datetime import timedelta
import random

class Command(BaseCommand):
    help = 'Tests the double-pick week elimination logic'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting double-pick elimination test'))
        
        # Create a test pool if needed
        try:
            pool = Pool.objects.get(name="Test Pool")
            self.stdout.write(self.style.SUCCESS(f'Using existing pool: {pool.name}'))
        except Pool.DoesNotExist:
            # Check if there's a superuser we can use as created_by
            from django.contrib.auth import get_user_model
            User = get_user_model()
            admin_user = User.objects.filter(is_superuser=True).first()
            
            if not admin_user:
                self.stdout.write(self.style.ERROR('No admin user found to create pool. Please create a superuser first.'))
                return
                
            pool = Pool.objects.create(
                name="Test Pool",
                year=2025,
                description='Test pool for elimination logic',
                created_by=admin_user,
                is_active=True
            )
            self.stdout.write(self.style.SUCCESS(f'Created test pool: {pool.name}'))
        
        # Get or create a test week
        week, created = Week.objects.get_or_create(
            number=99,  # Use a high number that won't conflict
            defaults={
                'start_date': timezone.now() - timedelta(days=7),  # Using datetime, not date
                'end_date': timezone.now() - timedelta(days=1),    # Using datetime, not date
                'deadline': timezone.now() - timedelta(days=2),
                'is_regular_season': True,
                'reset_pool': False,
                'description': 'Test Week for Double-Pick Elimination'
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created test week: Week {week.number}'))
        
        # Make this a double-pick week in settings
        settings, created = PoolWeekSettings.objects.get_or_create(
            pool=pool,
            week=week,
            defaults={
                'is_double': True
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created double-pick settings for Week {week.number}'))
        
        # Ensure we have a double-pick week
        settings.is_double = True
        settings.save()
        
        # Get some teams (we need at least 4)
        teams = list(Team.objects.all()[:4])
        if len(teams) < 4:
            self.stdout.write(self.style.ERROR('Not enough teams in database. Need at least 4.'))
            return
        
        # Get a user for our test entries
        from django.contrib.auth import get_user_model
        User = get_user_model()
        test_user = User.objects.filter(is_superuser=True).first()
        
        if not test_user:
            self.stdout.write(self.style.ERROR('No admin user found to create entries. Please create a superuser first.'))
            return
            
        # Create test entries
        test_entries = []
        for i in range(1, 5):
            try:
                # First try to get an existing entry
                entry = Entry.objects.get(entry_name=f"Test Entry {i}", pool=pool)
                # Reset it to alive
                entry.is_alive = True
                entry.eliminated_in_week = None
                entry.save()
                self.stdout.write(self.style.SUCCESS(f'Reset existing entry: {entry.entry_name}'))
            except Entry.DoesNotExist:
                # Create a new entry if it doesn't exist
                entry = Entry.objects.create(
                    entry_name=f"Test Entry {i}",
                    pool=pool,
                    user=test_user,
                    is_alive=True
                )
                self.stdout.write(self.style.SUCCESS(f'Created test entry: {entry.entry_name}'))
            
            # Add to our list of test entries
            test_entries.append(entry)
        
        # Create picks for each entry
        self.stdout.write(self.style.SUCCESS('Creating picks for test entries...'))
        
        # Entry 1: Two wins (should survive)
        self._create_pick(test_entries[0], week, teams[0])
        self._create_pick(test_entries[0], week, teams[1])
        
        # Entry 2: One win, one loss (should be eliminated)
        self._create_pick(test_entries[1], week, teams[0])
        self._create_pick(test_entries[1], week, teams[2])
        
        # Entry 3: Two losses (should be eliminated)
        self._create_pick(test_entries[2], week, teams[2])
        self._create_pick(test_entries[2], week, teams[3])
        
        # Entry 4: No picks yet
        
        # Process test results
        self.stdout.write(self.style.SUCCESS('Processing team results...'))
        
        # Teams 0 and 1 win, Teams 2 and 3 lose
        self._set_result(week, teams[0], 'win')
        self._set_result(week, teams[1], 'win')
        self._set_result(week, teams[2], 'loss')
        self._set_result(week, teams[3], 'loss')
        
        # Check entry statuses
        self.stdout.write(self.style.SUCCESS('\nResults:'))
        for entry in test_entries:
            # Refresh from DB
            entry.refresh_from_db()
            status = "ALIVE" if entry.is_alive else "ELIMINATED"
            self.stdout.write(f"{entry.entry_name}: {status}")
            
        # Expected results:
        # Entry 1: ALIVE (2 wins)
        # Entry 2: ELIMINATED (1 win, 1 loss)
        # Entry 3: ELIMINATED (2 losses)
        # Entry 4: ALIVE (no picks, not affected)
    
    def _create_pick(self, entry, week, team):
        # Try to get an existing pick
        try:
            pick = Pick.objects.get(entry=entry, week=week, team=team)
            self.stdout.write(f'  Using existing pick: {entry.entry_name} picking {team} for Week {week.number}')
        except Pick.DoesNotExist:
            # Create a new pick, bypassing validation with admin_request flag
            pick = Pick(entry=entry, week=week, team=team)
            # Bypass clean validation with admin_request flag
            pick.save(admin_request=True)
            self.stdout.write(f'  Created pick: {entry.entry_name} picking {team} for Week {week.number}')
        return pick
    
    def _set_result(self, week, team, result):
        # First, clear any existing result
        WeeklyResult.objects.filter(week=week, team=team).delete()
        
        # Create a new result
        weekly_result = WeeklyResult.objects.create(
            week=week,
            team=team,
            result=result
        )
        self.stdout.write(f'  Set result for {team} to {result}')
        
        # Return the created result
        return weekly_result
