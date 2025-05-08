import os
import django
import datetime
from zoneinfo import ZoneInfo

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lms2025.settings')
django.setup()

from pool.models import Week
from django.utils import timezone

# Get current week count
weeks_count = Week.objects.count()
print(f"Currently have {weeks_count} weeks in the database")

# If no weeks, create Week 1 for testing
if weeks_count == 0:
    # Pacific Time Zone
    pacific = ZoneInfo('America/Los_Angeles')
    
    # Make sure Week 1 covers the current date for testing
    today = timezone.now().date()
    start_date = today - datetime.timedelta(days=today.weekday())  # Start of this week (Monday)
    end_date = start_date + datetime.timedelta(days=6)  # End of this week (Sunday)
    
    # Set deadline to tomorrow 4pm to allow testing
    tomorrow = today + datetime.timedelta(days=1)
    deadline = datetime.datetime.combine(tomorrow, datetime.time(16, 0))
    deadline = deadline.replace(tzinfo=pacific)
    
    # Create Week 1
    Week.objects.create(
        number=1,
        description="Week 1 - Test Week",
        start_date=start_date,
        end_date=end_date,
        deadline=deadline,
        is_regular_season=True,
        is_double=False,
        reset_pool=False,
        reminder_time=deadline - datetime.timedelta(days=1, hours=6)
    )
    print(f"Created Week 1 covering {start_date} to {end_date} with deadline {deadline}")
else:
    # List all weeks
    weeks = Week.objects.all().order_by('number')
    print("Available weeks:")
    for week in weeks:
        print(f"Week {week.number}: {week.start_date} to {week.end_date}, deadline: {week.deadline}")
        
    # Check if any week covers today
    today = timezone.now().date()
    current_week = Week.objects.filter(
        start_date__lte=today,
        end_date__gte=today
    ).first()
    
    if current_week:
        print(f"Current week is Week {current_week.number}")
    else:
        print("No week covers today's date")

print("Done")
