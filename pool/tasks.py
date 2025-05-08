import logging
from django.conf import settings
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Count
from .models import Pool, Week, Pick, Team

logger = logging.getLogger(__name__)

def send_picks_report_email(pool_id, week_id):
    """
    Send a report email to all pool participants when the week's deadline passes.
    """
    try:
        pool = Pool.objects.get(id=pool_id)
        week = Week.objects.get(id=week_id)
        
        if not week.is_past_deadline():
            # Deadline hasn't passed yet, don't send report
            return
        
        # Get all picks for this week and pool
        picks = Pick.objects.filter(entry__pool=pool, week=week)
        
        # Group picks by team
        team_counts = {}
        for pick in picks:
            team_id = pick.team.id
            if team_id not in team_counts:
                team_counts[team_id] = {
                    'team': pick.team,
                    'entries': [],
                    'count': 0
                }
            team_counts[team_id]['entries'].append(pick.entry.entry_name)
            team_counts[team_id]['count'] += 1
        
        # Sort by count descending
        team_distribution = [team_counts[team_id] for team_id in team_counts]
        team_distribution.sort(key=lambda x: x['count'], reverse=True)
        
        # Get all participants' emails
        users = get_user_model().objects.filter(
            entry__pool=pool
        ).distinct()
        
        for user in users:
            # Get user's entries and their picks
            user_entries = user.entry_set.filter(pool=pool)
            user_picks = picks.filter(entry__in=user_entries)
            
            # Build email context
            context = {
                'user': user,
                'pool': pool,
                'week': week,
                'user_entries': user_entries,
                'user_picks': user_picks,
                'team_distribution': team_distribution,
            }
            
            # Render email templates
            subject = f"Week {week.number} Picks Report - {pool.name}"
            text_content = render_to_string('email/picks_report.txt', context)
            html_content = render_to_string('email/picks_report.html', context)
            
            # Create and send email
            email = EmailMultiAlternatives(
                subject,
                text_content,
                settings.DEFAULT_FROM_EMAIL,
                [user.email]
            )
            email.attach_alternative(html_content, "text/html")
            email.send()
            
            logger.info(f"Sent Week {week.number} picks report email to {user.email}")
            
    except Exception as e:
        logger.error(f"Error sending picks report email: {e}")
