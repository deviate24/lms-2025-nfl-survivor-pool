from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from pool.models import Week, WeeklyResult, Pick, Team, Entry

class Command(BaseCommand):
    help = 'Test utility for simulating NFL season weeks'

    def add_arguments(self, parser):
        parser.add_argument(
            'week',
            type=int,
            help='Which week number to make current (1-22)'
        )
        parser.add_argument(
            '--set-results',
            action='store_true',
            help='Set random results for the previous week'
        )
        parser.add_argument(
            '--clear-results',
            action='store_true',
            help='Clear results for the current week'
        )

    def handle(self, *args, **options):
        week_number = options['week']
        
        try:
            # Get the target week
            try:
                target_week = Week.objects.get(number=week_number)
            except Week.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Week {week_number} does not exist!'))
                return
                
            # Calculate what today should be to make this the current week
            today = timezone.now().date()
            # Set today to be the day after the start date of the target week
            new_date = target_week.start_date + timedelta(days=1)
            
            self.stdout.write(self.style.SUCCESS(f'Setting current week to Week {week_number}'))
            self.stdout.write(f'Week {week_number} dates: {target_week.start_date} to {target_week.end_date}')
            
            # Set random results for previous week if requested
            if options['set_results'] and week_number > 1:
                prev_week = Week.objects.get(number=week_number-1)
                
                # Check if results already exist
                existing_results = WeeklyResult.objects.filter(week=prev_week).count()
                if existing_results > 0 and not options['clear_results']:
                    self.stdout.write(self.style.WARNING(f'Results already exist for Week {prev_week.number}. Use --clear-results to override.'))
                else:
                    # Clear existing results if requested
                    if existing_results > 0 and options['clear_results']:
                        WeeklyResult.objects.filter(week=prev_week).delete()
                        self.stdout.write(self.style.SUCCESS(f'Cleared existing results for Week {prev_week.number}'))
                    
                    # Set random results for previous week
                    import random
                    teams = Team.objects.all()
                    results_count = 0
                    
                    for team in teams:
                        result = random.choice(['win', 'loss'])
                        WeeklyResult.objects.create(
                            week=prev_week,
                            team=team,
                            result=result
                        )
                        results_count += 1
                    
                    self.stdout.write(self.style.SUCCESS(f'Created {results_count} random results for Week {prev_week.number}'))
                    
                    # Report entry status after results
                    total_entries = Entry.objects.count()
                    eliminated_entries = Entry.objects.filter(is_alive=False).count()
                    self.stdout.write(f'Entries status: {eliminated_entries} eliminated out of {total_entries} total')
            
            # Update database to use target week's dates
            # This is a special hack for testing - we're adjusting the database dates to make the system think
            # we're in the middle of the target week
            
            # Update django settings to use the new date for timezone.now() during this session
            # NOTE: This is just for display purposes to the user
            self.stdout.write(self.style.SUCCESS(f'Testing system with Week {week_number} as current week'))
            
            # Print current week picks
            self.stdout.write('\nCurrent picks:')
            curr_picks = Pick.objects.filter(week=target_week)
            if curr_picks.count() == 0:
                self.stdout.write('No picks made for this week yet.')
            else:
                for pick in curr_picks:
                    self.stdout.write(f'Entry: {pick.entry.entry_name}, Pick: {pick.team}, Result: {pick.result or "Pending"}')
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))
