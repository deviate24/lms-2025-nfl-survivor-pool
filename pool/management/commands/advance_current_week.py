from django.core.management.base import BaseCommand
from django.utils import timezone
from pool.models import Week


class Command(BaseCommand):
    help = "Advance the current week by modifying week dates"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset", 
            action="store_true",
            help="Reset dates to their original values (stored in description)"
        )
        parser.add_argument(
            "--week",
            type=int,
            help="Manually set current week to specified number"
        )

    def handle(self, *args, **options):
        reset = options.get('reset', False)
        target_week_num = options.get('week')
        
        if reset:
            self._reset_weeks()
            return
            
        if target_week_num:
            self._set_specific_week(target_week_num)
            return
            
        # Default action: advance to next week
        self._advance_to_next_week()

    def _reset_weeks(self):
        """Reset all week dates to their original values."""
        weeks = Week.objects.all().order_by('number')
        
        for week in weeks:
            # Check if original dates are stored in description
            desc = week.description or ""
            
            if "Original:" in desc:
                try:
                    # Extract original dates from description if they exist
                    # Format should be "Original: YYYY-MM-DD to YYYY-MM-DD"
                    date_part = desc.split("Original:")[1].strip()
                    start_date_str, end_date_str = date_part.split(" to ")
                    
                    year, month, day = map(int, start_date_str.split("-"))
                    week.start_date = timezone.datetime(year, month, day).date()
                    
                    year, month, day = map(int, end_date_str.split("-"))
                    week.end_date = timezone.datetime(year, month, day).date()
                    
                    # Set deadline to start_date + 4 days at 4pm PT
                    deadline_date = week.start_date + timezone.timedelta(days=4)
                    deadline = timezone.datetime(
                        deadline_date.year,
                        deadline_date.month,
                        deadline_date.day,
                        16, 0, 0  # 4:00 PM
                    )
                    week.deadline = timezone.get_current_timezone().localize(deadline)
                    
                    week.save()
                    self.stdout.write(self.style.SUCCESS(f"Reset Week {week.number} dates to original values"))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Error resetting Week {week.number}: {e}"))
            else:
                self.stdout.write(self.style.WARNING(f"No original dates found for Week {week.number}"))
                
        self.stdout.write(self.style.SUCCESS("Week dates reset complete"))

    def _backup_original_dates(self, week):
        """Store original dates in description if not already there."""
        if not week.description or "Original:" not in week.description:
            original_info = f"Original: {week.start_date} to {week.end_date}"
            if week.description:
                week.description = f"{week.description} ({original_info})"
            else:
                week.description = original_info
            week.save()
            return True
        return False

    def _advance_to_next_week(self):
        """Find current week and advance to next week by adjusting dates."""
        # Get current week
        now = timezone.now().date()
        current_week = Week.objects.filter(
            start_date__lte=now,
            end_date__gte=now
        ).first()
        
        if not current_week:
            current_week = Week.objects.filter(
                start_date__gt=now
            ).order_by('start_date').first()
            
            if not current_week:
                self.stdout.write(self.style.ERROR("No current week found"))
                return
                
            self.stdout.write(self.style.WARNING(f"No active week found. Using future Week {current_week.number}"))
        
        # Get next week
        next_week = Week.objects.filter(
            number=current_week.number + 1
        ).first()
        
        if not next_week:
            self.stdout.write(self.style.ERROR(f"No week found after Week {current_week.number}"))
            return
            
        # Back up original dates if not already done
        self._backup_original_dates(current_week)
        self._backup_original_dates(next_week)
        
        # Set current week to be in the past
        current_start = timezone.now().date() - timezone.timedelta(days=14)
        current_end = current_start + timezone.timedelta(days=6)
        current_deadline = timezone.now() - timezone.timedelta(days=3)
        
        # Set next week to be current
        next_start = timezone.now().date() - timezone.timedelta(days=2)
        next_end = next_start + timezone.timedelta(days=6)
        next_deadline = timezone.now() + timezone.timedelta(days=1)  # Deadline tomorrow
        
        # Update weeks
        current_week.start_date = current_start
        current_week.end_date = current_end
        current_week.deadline = current_deadline
        current_week.save()
        
        next_week.start_date = next_start
        next_week.end_date = next_end
        next_week.deadline = next_deadline
        next_week.save()
        
        # Reset email_sent flag for next week if needed
        next_week.email_sent = False
        next_week.save(update_fields=['email_sent'])
        
        self.stdout.write(self.style.SUCCESS(
            f"Advanced from Week {current_week.number} to Week {next_week.number}.\n"
            f"Week {current_week.number} is now in the past ({current_start} to {current_end}).\n"
            f"Week {next_week.number} is now current ({next_start} to {next_end}).\n"
            f"Week {next_week.number} deadline: {next_deadline.strftime('%Y-%m-%d %H:%M:%S')}"
        ))

    def _set_specific_week(self, week_number):
        """Set a specific week as the current week."""
        target_week = Week.objects.filter(number=week_number).first()
        if not target_week:
            self.stdout.write(self.style.ERROR(f"Week {week_number} not found"))
            return

        # Back up original date
        self._backup_original_dates(target_week)
        
        # Set target week to be current
        today = timezone.now().date()
        target_week.start_date = today - timezone.timedelta(days=2)
        target_week.end_date = today + timezone.timedelta(days=4)
        
        # Deadline tomorrow at 4pm
        tomorrow = today + timezone.timedelta(days=1)
        deadline_dt = timezone.datetime(
            tomorrow.year, tomorrow.month, tomorrow.day, 16, 0, 0
        )
        target_week.deadline = timezone.get_current_timezone().localize(deadline_dt)
        target_week.save()
        
        # Set previous weeks to be in the past
        for prev_week in Week.objects.filter(number__lt=week_number):
            self._backup_original_dates(prev_week)
            
            past_start = today - timezone.timedelta(days=14 + (week_number - prev_week.number) * 7)
            past_end = past_start + timezone.timedelta(days=6)
            past_deadline = timezone.now() - timezone.timedelta(days=3 + (week_number - prev_week.number) * 7)
            
            prev_week.start_date = past_start
            prev_week.end_date = past_end
            prev_week.deadline = past_deadline
            prev_week.save()
            
        # Set future weeks
        for future_week in Week.objects.filter(number__gt=week_number):
            self._backup_original_dates(future_week)
            
            future_start = today + timezone.timedelta(days=5 + (future_week.number - week_number) * 7)
            future_end = future_start + timezone.timedelta(days=6)
            future_deadline_date = future_start + timezone.timedelta(days=4)
            future_deadline_dt = timezone.datetime(
                future_deadline_date.year, 
                future_deadline_date.month, 
                future_deadline_date.day, 
                16, 0, 0
            )
            future_deadline = timezone.get_current_timezone().localize(future_deadline_dt)
            
            future_week.start_date = future_start
            future_week.end_date = future_end
            future_week.deadline = future_deadline
            future_week.save()
        
        self.stdout.write(self.style.SUCCESS(
            f"Set Week {week_number} as current week.\n"
            f"Week {week_number}: {target_week.start_date} to {target_week.end_date}\n"
            f"Deadline: {target_week.deadline.strftime('%Y-%m-%d %H:%M:%S')}"
        ))
