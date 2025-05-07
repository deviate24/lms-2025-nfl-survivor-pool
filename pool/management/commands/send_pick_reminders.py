import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings

from pool.models import Week, Entry, Pick, Pool


class Command(BaseCommand):
    help = 'Send reminder emails to users who have not made picks for the current week'
    
    def handle(self, *args, **options):
        logger = logging.getLogger(__name__)
        
        # Get the current week
        current_week = Week.objects.filter(
            start_date__lte=timezone.now().date(),
            end_date__gte=timezone.now().date()
        ).first()
        
        # If no current week, get the next upcoming week
        if not current_week:
            current_week = Week.objects.filter(
                start_date__gt=timezone.now().date()
            ).order_by('start_date').first()
        
        if not current_week:
            self.stdout.write(self.style.WARNING('No current or upcoming week found'))
            return
        
        # Check if we should send reminders today
        # By default, send reminders on Tuesday at 9:00 AM PT
        # If the week has a custom reminder_time, use that instead
        now = timezone.now()
        
        if current_week.reminder_time:
            should_send = now >= current_week.reminder_time
        else:
            # Default to Tuesday 9:00 AM PT
            deadline = current_week.deadline
            days_before_deadline = 2  # Tuesday is typically 2 days before Thursday
            default_reminder_time = deadline - timedelta(days=days_before_deadline)
            default_reminder_time = default_reminder_time.replace(hour=9, minute=0, second=0)
            
            should_send = now >= default_reminder_time
        
        if not should_send:
            self.stdout.write(self.style.WARNING('Not time to send reminders yet'))
            return
        
        # Check if the deadline has passed
        if current_week.is_past_deadline():
            self.stdout.write(self.style.WARNING(f'Deadline for Week {current_week.number} has passed'))
            return
        
        # Get all active pools
        active_pools = Pool.objects.filter(is_active=True)
        
        reminders_sent = 0
        
        for pool in active_pools:
            # Get all alive entries in this pool
            alive_entries = Entry.objects.filter(pool=pool, is_alive=True)
            
            for entry in alive_entries:
                # Check if the entry has made a pick for the current week
                picks = Pick.objects.filter(entry=entry, week=current_week)
                
                # For double-pick weeks, need two picks
                if current_week.is_double and picks.count() < 2:
                    self.send_reminder(entry, current_week)
                    reminders_sent += 1
                # For regular weeks, need one pick
                elif not current_week.is_double and picks.count() < 1:
                    self.send_reminder(entry, current_week)
                    reminders_sent += 1
        
        self.stdout.write(self.style.SUCCESS(f'Sent {reminders_sent} reminder emails'))
    
    def send_reminder(self, entry, week):
        """
        Send a reminder email to the user for the given entry and week.
        """
        user_email = entry.user.email
        
        # Prepare the email content
        context = {
            'user': entry.user,
            'entry': entry,
            'week': week,
            'is_double_pick': week.is_double,
            'deadline': week.deadline,
        }
        
        # Render the HTML email template
        html_message = render_to_string('pool/email/pick_reminder.html', context)
        plain_message = strip_tags(html_message)
        
        # Send the email
        try:
            send_mail(
                subject=f'LMS 2025: Week {week.number} Pick Reminder for {entry.entry_name}',
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user_email],
                html_message=html_message,
                fail_silently=False,
            )
            self.stdout.write(f'Sent reminder to {user_email} for {entry.entry_name}')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error sending reminder to {user_email}: {e}'))
