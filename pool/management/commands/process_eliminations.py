from django.core.management.base import BaseCommand
from django.utils import timezone
from pool.models import Week, Entry, Pick, AuditLog


class Command(BaseCommand):
    help = 'Process eliminations for entries without picks after the deadline'

    def handle(self, *args, **options):
        # Get the current time
        now = timezone.now()
        
        # Find all weeks where the deadline has passed but we're still within the week's end date
        active_weeks = Week.objects.filter(
            deadline__lt=now,
            end_date__gte=now
        )
        
        if not active_weeks.exists():
            self.stdout.write(self.style.WARNING('No weeks with passed deadlines found'))
            return
        
        for week in active_weeks:
            self.stdout.write(self.style.SUCCESS(f'Processing eliminations for Week {week.number}'))
            
            # Get all active entries across all pools
            active_entries = Entry.objects.filter(is_alive=True)
            
            # Count how many were eliminated
            eliminated_count = 0
            
            for entry in active_entries:
                # Check if this entry has a pick for this week
                has_pick = Pick.objects.filter(entry=entry, week=week).exists()
                
                if not has_pick:
                    # No pick was made before the deadline - eliminate the entry
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
            
            self.stdout.write(self.style.SUCCESS(
                f'Eliminated {eliminated_count} entries for Week {week.number} due to no picks'
            ))
