from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from pool.models import Week, WeeklyResult, Pick

class Command(BaseCommand):
    help = 'Simulates advancing to the next week in the NFL Survivor Pool'

    def add_arguments(self, parser):
        parser.add_argument(
            '--set-results',
            action='store_true',
            help='Automatically set random results for all teams in the current week',
        )

    def handle(self, *args, **options):
        try:
            # Find all weeks ordered by number
            weeks = Week.objects.all().order_by('number')
            if not weeks.exists():
                self.stdout.write(self.style.ERROR('No weeks found!'))
                return
                
            # Find the current week (week whose start/end dates include today)
            today = timezone.now().date()
            current_week = None
            for week in weeks:
                if week.start_date <= today <= week.end_date:
                    current_week = week
                    break
            
            if not current_week:
                self.stdout.write(self.style.ERROR('Could not determine current week!'))
                return
                
            # Find the next week
            next_week = None
            for week in weeks:
                if week.number == current_week.number + 1:
                    next_week = week
                    break
                    
            if not next_week:
                self.stdout.write(self.style.ERROR(f'Week {current_week.number + 1} does not exist!'))
                return
            
            # Create game results if requested
            if options['set_results']:
                import random
                from pool.models import Team
                teams = Team.objects.all()
                
                # Check for existing results
                existing_results = WeeklyResult.objects.filter(week=current_week).count()
                if existing_results > 0:
                    self.stdout.write(self.style.WARNING(f'Results already exist for Week {current_week.number}. Skipping result creation.'))
                else:
                    # Create random results for all teams
                    for team in teams:
                        result = random.choice(['win', 'loss'])
                        WeeklyResult.objects.create(
                            week=current_week,
                            team=team,
                            result=result
                        )
                    self.stdout.write(self.style.SUCCESS(f'Created random results for {teams.count()} teams in Week {current_week.number}'))
                
            # Update the dates to make the next week current
            # Calculate days to shift
            days_to_shift = (next_week.start_date - current_week.start_date).days
            
            # Make today the first day of the next week
            new_today = next_week.start_date
            time_shift = new_today - today
            
            # Update all weeks
            for week in weeks:
                # Update with a nice time buffer
                if week.number < current_week.number:
                    # Past weeks stay in the past
                    pass
                elif week.number == current_week.number:
                    # Make current week in the past
                    week.end_date = new_today - timedelta(days=1)
                    week.deadline = timezone.now() - timedelta(days=1)
                    week.save()
                else:
                    # Shift future weeks forward
                    week.start_date = week.start_date - time_shift
                    week.end_date = week.end_date - time_shift
                    week.deadline = week.deadline - time_shift
                    week.save()
            
            self.stdout.write(self.style.SUCCESS(f'Successfully advanced from Week {current_week.number} to Week {next_week.number}'))
            self.stdout.write(self.style.SUCCESS(f'Today is now considered to be within Week {next_week.number}'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))
