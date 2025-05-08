from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, timedelta
from pool.models import Week
from zoneinfo import ZoneInfo

class Command(BaseCommand):
    help = 'Sets up test weeks for the 2025 NFL season'

    def handle(self, *args, **options):
        # Delete existing weeks
        Week.objects.all().delete()
        
        # Create 5 weeks starting from September 4, 2025
        tz = ZoneInfo('America/Los_Angeles')
        start_date = datetime(2025, 9, 1).date()  # Monday
        
        for week_num in range(1, 6):
            end_date = start_date + timedelta(days=6)  # Sunday
            deadline = datetime.combine(start_date + timedelta(days=3), 
                                     datetime.strptime('16:00', '%H:%M').time())  # Thursday 4 PM
            deadline = deadline.replace(tzinfo=tz)
            
            reminder = datetime.combine(start_date + timedelta(days=2), 
                                     datetime.strptime('10:00', '%H:%M').time())  # Wednesday 10 AM
            reminder = reminder.replace(tzinfo=tz)
            
            Week.objects.create(
                number=week_num,
                description=f"Week {week_num}" + (" - Double Pick Week" if week_num == 5 else ""),
                start_date=start_date,
                end_date=end_date,
                deadline=deadline,
                is_regular_season=True,
                is_double=(week_num == 5),  # Week 5 is double pick
                reset_pool=False,
                reminder_time=reminder
            )
            
            start_date += timedelta(days=7)  # Move to next week
            
        self.stdout.write(self.style.SUCCESS('Successfully created test weeks'))
