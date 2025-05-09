from django.core.management.base import BaseCommand
from django.utils import timezone
from pool.models import Week
import datetime

class Command(BaseCommand):
    help = 'Updates all weeks to a compressed testing schedule'

    def handle(self, *args, **options):
        # Delete any existing weeks
        Week.objects.all().delete()
        
        # Start date and time for Week 1
        today = timezone.now().date()
        start_date = timezone.datetime(today.year, today.month, today.day, 8, 30, 0, tzinfo=timezone.get_current_timezone())
        
        # Create weeks with the specified pattern
        for week_number in range(1, 19):  # Regular season weeks 1-18
            # Calculate times based on pattern
            deadline = start_date + datetime.timedelta(minutes=5)
            end_date = deadline + datetime.timedelta(minutes=3)
            
            # Create the week
            week = Week.objects.create(
                number=week_number,
                description=f"Week {week_number}",
                start_date=start_date,
                end_date=end_date,
                deadline=deadline,
                is_regular_season=True,
                reset_pool=False
            )
            
            self.stdout.write(self.style.SUCCESS(
                f'Created Week {week_number}: '
                f'Start: {start_date.strftime("%Y-%m-%d %H:%M:%S")}, '
                f'Deadline: {deadline.strftime("%Y-%m-%d %H:%M:%S")}, '
                f'End: {end_date.strftime("%Y-%m-%d %H:%M:%S")}'
            ))
            
            # Next week starts 2 minutes after this week ends
            start_date = end_date + datetime.timedelta(minutes=2)
        
        # Create playoff weeks (19-22)
        for playoff_week in range(19, 23):
            # Calculate times based on pattern
            deadline = start_date + datetime.timedelta(minutes=5)
            end_date = deadline + datetime.timedelta(minutes=3)
            
            # Playoff week descriptions
            if playoff_week == 19:
                description = "Wild Card Round"
            elif playoff_week == 20:
                description = "Divisional Round"
            elif playoff_week == 21:
                description = "Conference Championships"
            else:
                description = "Super Bowl"
            
            # Create playoff week
            week = Week.objects.create(
                number=playoff_week,
                description=description,
                start_date=start_date,
                end_date=end_date,
                deadline=deadline,
                is_regular_season=False,
                reset_pool=(playoff_week == 19)  # Reset pool for Wild Card Round
            )
            
            self.stdout.write(self.style.SUCCESS(
                f'Created Playoff Week {playoff_week} ({description}): '
                f'Start: {start_date.strftime("%Y-%m-%d %H:%M:%S")}, '
                f'Deadline: {deadline.strftime("%Y-%m-%d %H:%M:%S")}, '
                f'End: {end_date.strftime("%Y-%m-%d %H:%M:%S")}'
            ))
            
            # Next week starts 2 minutes after this week ends
            start_date = end_date + datetime.timedelta(minutes=2)
        
        self.stdout.write(self.style.SUCCESS('Successfully updated all weeks for compressed testing schedule'))
