from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from .models import Pick, PoolWeekSettings


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
