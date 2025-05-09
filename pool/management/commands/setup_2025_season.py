from django.core.management.base import BaseCommand
from django.utils import timezone
from pool.models import Week
import datetime

class Command(BaseCommand):
    help = 'Creates a realistic 2025 NFL season schedule'

    def handle(self, *args, **options):
        # Delete any existing weeks
        Week.objects.all().delete()
        
        # Start date for Week 1 of 2025 NFL Season (Thursday, Sept 4, 2025)
        start_date = timezone.datetime(2025, 9, 4, 20, 20, 0, tzinfo=timezone.get_current_timezone())
        
        # Create regular season weeks (1-18)
        for week_number in range(1, 19):
            # Calculate week dates
            # Week starts on Thursday
            week_start = start_date + datetime.timedelta(days=(week_number-1)*7)
            # Deadline is Sunday morning before games
            deadline = week_start + datetime.timedelta(days=3, hours=9)  # Sunday at 9am
            # Week ends after Monday Night Football
            week_end = week_start + datetime.timedelta(days=4, hours=23, minutes=59)  # Monday at 11:59pm
            
            # Create the week
            week = Week.objects.create(
                number=week_number,
                description=f"Week {week_number}",
                start_date=week_start,
                end_date=week_end,
                deadline=deadline,
                is_regular_season=True,
                reset_pool=False
            )
            
            self.stdout.write(self.style.SUCCESS(
                f'Created Week {week_number}: '
                f'Start: {week_start.strftime("%Y-%m-%d %H:%M:%S")}, '
                f'Deadline: {deadline.strftime("%Y-%m-%d %H:%M:%S")}, '
                f'End: {week_end.strftime("%Y-%m-%d %H:%M:%S")}'
            ))
        
        # Create playoff weeks (19-22)
        playoff_descriptions = {
            19: "Wild Card Round",
            20: "Divisional Round",
            21: "Conference Championships",
            22: "Super Bowl LX"
        }
        
        # First playoff week starts after the last regular season week
        playoff_start = Week.objects.get(number=18).end_date + datetime.timedelta(days=3)
        
        for playoff_week in range(19, 23):
            # Each playoff round is one week apart
            week_start = playoff_start + datetime.timedelta(days=(playoff_week-19)*7)
            deadline = week_start + datetime.timedelta(days=3, hours=9)  # Sunday at 9am
            week_end = week_start + datetime.timedelta(days=4, hours=23, minutes=59)
            
            # Super Bowl is special - usually 2 weeks after Championship games
            if playoff_week == 22:
                week_start = week_start + datetime.timedelta(days=7)  # Extra week before Super Bowl
                deadline = week_start + datetime.timedelta(days=3, hours=9)
                week_end = week_start + datetime.timedelta(days=4, hours=23, minutes=59)
            
            # Create the playoff week
            week = Week.objects.create(
                number=playoff_week,
                description=playoff_descriptions[playoff_week],
                start_date=week_start,
                end_date=week_end,
                deadline=deadline,
                is_regular_season=False,
                reset_pool=False
            )
            
            self.stdout.write(self.style.SUCCESS(
                f'Created Week {playoff_week} ({playoff_descriptions[playoff_week]}): '
                f'Start: {week_start.strftime("%Y-%m-%d %H:%M:%S")}, '
                f'Deadline: {deadline.strftime("%Y-%m-%d %H:%M:%S")}, '
                f'End: {week_end.strftime("%Y-%m-%d %H:%M:%S")}'
            ))
        
        self.stdout.write(self.style.SUCCESS('Successfully created 2025 NFL season schedule'))
