from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils import timezone
from django.db.models import F

from .models import Pick, PoolWeekSettings, Week, Pool
from .tasks import send_picks_report_email


@receiver(post_save, sender=Pick)
def send_confirmation_email(sender, instance, created, **kwargs):
    """
    Send a confirmation email when a pick is created or updated.
    This is triggered by the post_save signal on the Pick model.
    """
    if created:  # Only send on creation, not updates
        # Get the user's email
        user_email = instance.entry.user.email
        
        # Get the pool-specific settings for this week
        week_settings = PoolWeekSettings.objects.filter(
            pool=instance.entry.pool,
            week=instance.week
        ).first()
        
        # Default to False if no settings are found
        is_double_pick = False
        if week_settings:
            is_double_pick = week_settings.is_double
        
        # Prepare the email content
        context = {
            'user': instance.entry.user,
            'entry': instance.entry,
            'pick': instance,
            'week': instance.week,
            'team': instance.team,
            'is_double_pick': is_double_pick,
        }
        
        # Render the HTML email template
        html_message = render_to_string('pool/email/pick_confirmation.html', context)
        plain_message = strip_tags(html_message)
        
        # Send the email
        try:
            send_mail(
                subject=f'LMS 2025: Week {instance.week.number} Pick Confirmation',
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user_email],
                html_message=html_message,
                fail_silently=False,
            )
        except Exception as e:
            # Log the error but don't crash the app
            print(f"Error sending confirmation email: {e}")


def check_deadlines_and_send_reports():
    """
    Check for weeks with passed deadlines that haven't had reports sent yet.
    This should be called by a scheduled task or management command.
    """
    # Find weeks where the deadline has passed but emails haven't been sent
    now = timezone.now()
    weeks_needing_emails = Week.objects.filter(
        deadline__lte=now,  # Deadline has passed
        email_sent=False    # Emails haven't been sent yet
    )
    
    for week in weeks_needing_emails:
        # Get all pools that include this week
        pools = Pool.objects.filter(weeks=week, is_active=True)
        
        for pool in pools:
            # Send email report for this pool and week
            try:
                send_picks_report_email(pool.id, week.id)
                print(f"Sent pick reports for {pool.name}, Week {week.number}")
            except Exception as e:
                print(f"Error sending pick reports for {pool.name}, Week {week.number}: {e}")
        
        # Mark emails as sent for this week
        week.email_sent = True
        week.save(update_fields=['email_sent'])


@receiver(post_save, sender=Week)
def handle_week_deadline(sender, instance, **kwargs):
    """
    Check if a week's deadline has just passed and send email reports if needed.
    """
    # Check if this week's deadline has passed but emails haven't been sent
    now = timezone.now()
    if instance.deadline <= now and not instance.email_sent:
        # Get all pools that include this week
        pools = Pool.objects.filter(weeks=instance, is_active=True)
        
        for pool in pools:
            # Send email report for this pool and week
            try:
                send_picks_report_email(pool.id, instance.id)
                print(f"Sent pick reports for {pool.name}, Week {instance.number}")
            except Exception as e:
                print(f"Error sending pick reports for {pool.name}, Week {instance.number}: {e}")
        
        # Mark emails as sent for this week
        instance.email_sent = True
        instance.save(update_fields=['email_sent'])
