import os
import django
import datetime
from zoneinfo import ZoneInfo

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lms2025.settings')
django.setup()

from pool.models import Week

# Clear existing weeks
Week.objects.all().delete()

# Pacific Time Zone
pacific = ZoneInfo('America/Los_Angeles')

# Create weeks
weeks_data = [
    # Regular Season
    (1, 'Week 1', datetime.date(2025, 9, 1), datetime.date(2025, 9, 7), 
     datetime.datetime(2025, 9, 4, 16, 0, tzinfo=pacific), True, False, False),
    
    (2, 'Week 2', datetime.date(2025, 9, 8), datetime.date(2025, 9, 14), 
     datetime.datetime(2025, 9, 11, 16, 0, tzinfo=pacific), True, False, False),
    
    (3, 'Week 3', datetime.date(2025, 9, 15), datetime.date(2025, 9, 21), 
     datetime.datetime(2025, 9, 18, 16, 0, tzinfo=pacific), True, False, False),
    
    (4, 'Week 4', datetime.date(2025, 9, 22), datetime.date(2025, 9, 28), 
     datetime.datetime(2025, 9, 25, 16, 0, tzinfo=pacific), True, False, False),
    
    (5, 'Week 5', datetime.date(2025, 9, 29), datetime.date(2025, 10, 5), 
     datetime.datetime(2025, 10, 2, 16, 0, tzinfo=pacific), True, False, False),
    
    (6, 'Week 6', datetime.date(2025, 10, 6), datetime.date(2025, 10, 12), 
     datetime.datetime(2025, 10, 9, 16, 0, tzinfo=pacific), True, False, False),
    
    (7, 'Week 7', datetime.date(2025, 10, 13), datetime.date(2025, 10, 19), 
     datetime.datetime(2025, 10, 16, 16, 0, tzinfo=pacific), True, False, False),
    
    (8, 'Week 8', datetime.date(2025, 10, 20), datetime.date(2025, 10, 26), 
     datetime.datetime(2025, 10, 23, 16, 0, tzinfo=pacific), True, False, False),
    
    (9, 'Week 9', datetime.date(2025, 10, 27), datetime.date(2025, 11, 2), 
     datetime.datetime(2025, 10, 30, 16, 0, tzinfo=pacific), True, False, False),
    
    (10, 'Week 10', datetime.date(2025, 11, 3), datetime.date(2025, 11, 9), 
     datetime.datetime(2025, 11, 6, 16, 0, tzinfo=pacific), True, False, False),
    
    (11, 'Week 11', datetime.date(2025, 11, 10), datetime.date(2025, 11, 16), 
     datetime.datetime(2025, 11, 13, 16, 0, tzinfo=pacific), True, False, False),
    
    (12, 'Week 12', datetime.date(2025, 11, 17), datetime.date(2025, 11, 23), 
     datetime.datetime(2025, 11, 20, 16, 0, tzinfo=pacific), True, False, False),
    
    (13, 'Week 13 - Thanksgiving', datetime.date(2025, 11, 24), datetime.date(2025, 11, 30), 
     datetime.datetime(2025, 11, 27, 11, 0, tzinfo=pacific), True, False, False),
    
    (14, 'Week 14', datetime.date(2025, 12, 1), datetime.date(2025, 12, 7), 
     datetime.datetime(2025, 12, 4, 16, 0, tzinfo=pacific), True, True, False), # Double pick week
    
    (15, 'Week 15', datetime.date(2025, 12, 8), datetime.date(2025, 12, 14), 
     datetime.datetime(2025, 12, 11, 16, 0, tzinfo=pacific), True, False, False),
    
    (16, 'Week 16', datetime.date(2025, 12, 15), datetime.date(2025, 12, 21), 
     datetime.datetime(2025, 12, 18, 16, 0, tzinfo=pacific), True, False, False),
    
    (17, 'Week 17', datetime.date(2025, 12, 22), datetime.date(2025, 12, 28), 
     datetime.datetime(2025, 12, 25, 16, 0, tzinfo=pacific), True, False, False),
    
    (18, 'Week 18', datetime.date(2025, 12, 29), datetime.date(2026, 1, 4), 
     datetime.datetime(2026, 1, 1, 16, 0, tzinfo=pacific), True, False, False),
    
    # Playoffs
    (19, 'Wild Card Weekend', datetime.date(2026, 1, 5), datetime.date(2026, 1, 11), 
     datetime.datetime(2026, 1, 8, 16, 0, tzinfo=pacific), False, False, True),
    
    (20, 'Divisional Round', datetime.date(2026, 1, 12), datetime.date(2026, 1, 18), 
     datetime.datetime(2026, 1, 15, 16, 0, tzinfo=pacific), False, False, False),
    
    (21, 'Conference Championships', datetime.date(2026, 1, 19), datetime.date(2026, 1, 25), 
     datetime.datetime(2026, 1, 22, 16, 0, tzinfo=pacific), False, False, False),
    
    (22, 'Super Bowl LX', datetime.date(2026, 1, 26), datetime.date(2026, 2, 1), 
     datetime.datetime(2026, 1, 29, 16, 0, tzinfo=pacific), False, False, False)
]

# Create reminder time (1 day before deadline at 10 AM)
for number, description, start_date, end_date, deadline, is_regular_season, is_double, reset_pool in weeks_data:
    reminder_time = deadline - datetime.timedelta(days=1)
    reminder_time = reminder_time.replace(hour=10, minute=0, second=0)
    
    Week.objects.create(
        number=number,
        description=description,
        start_date=start_date,
        end_date=end_date,
        deadline=deadline,
        is_regular_season=is_regular_season,
        is_double=is_double,
        reset_pool=reset_pool,
        reminder_time=reminder_time
    )

print(f"Created {len(weeks_data)} weeks for the 2025 NFL season")
