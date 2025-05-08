from django.core.management.base import BaseCommand
from django.utils import timezone
from pool.models import Week, Pool
from pool.signals import check_deadlines_and_send_reports
from pool.tasks import send_picks_report_email


class Command(BaseCommand):
    help = "Sends pick report emails for weeks with deadlines that have passed"

    def add_arguments(self, parser):
        parser.add_argument(
            "--week", 
            type=int,
            help="Week number to send reports for (optional)"
        )
        parser.add_argument(
            "--pool", 
            type=int,
            help="Pool ID to send reports for (optional)"
        )
        parser.add_argument(
            "--force", 
            action="store_true",
            help="Force sending emails even if already sent"
        )

    def handle(self, *args, **options):
        week_num = options.get('week')
        pool_id = options.get('pool')
        force = options.get('force')
        
        if week_num and pool_id:
            # Send reports for specific week and pool
            try:
                week = Week.objects.get(number=week_num)
                pool = Pool.objects.get(id=pool_id)
                
                if not week.is_past_deadline() and not force:
                    self.stdout.write(
                        self.style.WARNING(f"Week {week.number} deadline hasn't passed yet. Use --force to send anyway.")
                    )
                    return
                
                if week.email_sent and not force:
                    self.stdout.write(
                        self.style.WARNING(f"Emails for Week {week.number} have already been sent. Use --force to resend.")
                    )
                    return
                
                send_picks_report_email(pool.id, week.id)
                
                if force and week.email_sent:
                    self.stdout.write(
                        self.style.SUCCESS(f"Re-sent pick reports for {pool.name}, Week {week.number}")
                    )
                else:
                    week.email_sent = True
                    week.save(update_fields=['email_sent'])
                    self.stdout.write(
                        self.style.SUCCESS(f"Sent pick reports for {pool.name}, Week {week.number}")
                    )
                
            except Week.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"Week {week_num} not found"))
            except Pool.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"Pool {pool_id} not found"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error: {e}"))
                
        elif week_num:
            # Send reports for specific week in all pools
            try:
                week = Week.objects.get(number=week_num)
                
                if not week.is_past_deadline() and not force:
                    self.stdout.write(
                        self.style.WARNING(f"Week {week.number} deadline hasn't passed yet. Use --force to send anyway.")
                    )
                    return
                
                if week.email_sent and not force:
                    self.stdout.write(
                        self.style.WARNING(f"Emails for Week {week.number} have already been sent. Use --force to resend.")
                    )
                    return
                
                pools = Pool.objects.filter(weeks=week, is_active=True)
                for pool in pools:
                    send_picks_report_email(pool.id, week.id)
                    self.stdout.write(
                        self.style.SUCCESS(f"Sent pick reports for {pool.name}, Week {week.number}")
                    )
                
                if not force:  # Only update if not forcing resend
                    week.email_sent = True
                    week.save(update_fields=['email_sent'])
                
            except Week.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"Week {week_num} not found"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error: {e}"))
                
        elif pool_id:
            # Send reports for current week in specific pool
            try:
                pool = Pool.objects.get(id=pool_id)
                # Find current week
                now = timezone.now().date()
                current_week = Week.objects.filter(
                    start_date__lte=now,
                    end_date__gte=now
                ).first()
                
                if not current_week:
                    self.stdout.write(self.style.ERROR("No current week found"))
                    return
                
                if not current_week.is_past_deadline() and not force:
                    self.stdout.write(
                        self.style.WARNING(f"Week {current_week.number} deadline hasn't passed yet. Use --force to send anyway.")
                    )
                    return
                
                if current_week.email_sent and not force:
                    self.stdout.write(
                        self.style.WARNING(f"Emails for Week {current_week.number} have already been sent. Use --force to resend.")
                    )
                    return
                
                send_picks_report_email(pool.id, current_week.id)
                
                if force and current_week.email_sent:
                    self.stdout.write(
                        self.style.SUCCESS(f"Re-sent pick reports for {pool.name}, Week {current_week.number}")
                    )
                else:
                    current_week.email_sent = True
                    current_week.save(update_fields=['email_sent'])
                    self.stdout.write(
                        self.style.SUCCESS(f"Sent pick reports for {pool.name}, Week {current_week.number}")
                    )
                
            except Pool.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"Pool {pool_id} not found"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error: {e}"))
                
        else:
            # Check all deadlines and send reports as needed
            self.stdout.write("Checking for weeks with passed deadlines...")
            check_deadlines_and_send_reports()
            self.stdout.write(self.style.SUCCESS("Finished sending pick reports"))
