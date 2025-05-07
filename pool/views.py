from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count, Q
from .models import Entry, Pick, Week, Pool, PoolWeekSettings

from .models import Pool, Entry, Pick, Week, Team
from .forms import PickForm, DoublePickForm, QuickPickForm


@login_required
def home(request):
    """
    Home page view showing the user's pools and entries.
    """
    # Get all pools the user has entries in
    user_pools = Pool.objects.filter(entries__user=request.user).distinct()
    
    # Get current week
    current_week = Week.objects.filter(
        start_date__lte=timezone.now().date(),
        end_date__gte=timezone.now().date()
    ).first()
    
    # If no current week, get the next upcoming week
    if not current_week:
        current_week = Week.objects.filter(
            start_date__gt=timezone.now().date()
        ).order_by('start_date').first()
    
    context = {
        'user_pools': user_pools,
        'current_week': current_week,
    }
    
    return render(request, 'pool/home.html', context)


@login_required
def pool_detail(request, pool_id):
    """
    View showing details of a specific pool.
    """
    pool = get_object_or_404(Pool, id=pool_id)
    
    # Get user's entries in this pool
    user_entries = Entry.objects.filter(pool=pool, user=request.user)
    
    # Get current week
    current_week = Week.objects.filter(
        start_date__lte=timezone.now().date(),
        end_date__gte=timezone.now().date()
    ).first()
    
    # If no current week, get the next upcoming week
    if not current_week:
        current_week = Week.objects.filter(
            start_date__gt=timezone.now().date()
        ).order_by('start_date').first()
    
    # Get all entries in this pool
    all_entries = Entry.objects.filter(pool=pool)
    alive_entries = all_entries.filter(is_alive=True)
    eliminated_entries = all_entries.filter(is_alive=False)
    
    context = {
        'pool': pool,
        'user_entries': user_entries,
        'current_week': current_week,
        'alive_entries': alive_entries,
        'eliminated_entries': eliminated_entries,
    }
    
    return render(request, 'pool/pool_detail.html', context)


@login_required
def entry_detail(request, entry_id):
    """
    View showing details of a specific entry.
    """
    entry = get_object_or_404(Entry, id=entry_id)
    
    # Check if user owns this entry
    if entry.user != request.user:
        messages.error(request, "You do not have permission to view this entry.")
        return redirect('home')
    
    # Get all picks for this entry
    picks = Pick.objects.filter(entry=entry).order_by('week__number')
    
    # Get current week
    current_week = Week.objects.filter(
        start_date__lte=timezone.now().date(),
        end_date__gte=timezone.now().date()
    ).first()
    
    # If no current week, get the next upcoming week
    if not current_week:
        current_week = Week.objects.filter(
            start_date__gt=timezone.now().date()
        ).order_by('start_date').first()
    
    # Check if user has made a pick for the current week
    current_week_picks = picks.filter(week=current_week)
    has_current_pick = current_week_picks.exists()
    
    # Get available teams
    available_teams = entry.get_available_teams(current_week)
    
    # Get pool-specific settings for current week
    is_double_pick = False
    if current_week:
        week_settings = PoolWeekSettings.objects.filter(
            pool=entry.pool,
            week=current_week
        ).first()
        if week_settings:
            is_double_pick = week_settings.is_double
    
    context = {
        'entry': entry,
        'picks': picks,
        'current_week': current_week,
        'has_current_pick': has_current_pick,
        'current_week_picks': current_week_picks,
        'available_teams': available_teams,
        'is_double_pick': is_double_pick,
    }
    
    return render(request, 'pool/entry_detail.html', context)


@login_required
def make_pick(request, entry_id):
    """
    View for making a pick for a specific entry.
    """
    entry = get_object_or_404(Entry, id=entry_id)
    
    # Check if user owns this entry
    if entry.user != request.user:
        messages.error(request, "You do not have permission to make picks for this entry.")
        return redirect('home')
    
    # Get current week
    today = timezone.now().date()
    current_week = Week.objects.filter(
        start_date__lte=today,
        end_date__gte=today
    ).first()
    
    # If no current week, get the next upcoming week
    if not current_week:
        current_week = Week.objects.filter(
            start_date__gt=today
        ).order_by('start_date').first()
    
    # If still no current week, fallback to the first week in the database
    if not current_week:
        current_week = Week.objects.all().order_by('number').first()
        
    # Debug info
    print(f"Selected Week: {current_week}")
    
    # Check if deadline has passed
    if current_week.is_past_deadline():
        messages.error(request, f"The deadline for Week {current_week.number} has passed.")
        return redirect('entry_detail', entry_id=entry.id)
    
    # Check if entry is still alive
    if not entry.is_alive:
        messages.error(request, "This entry has been eliminated and cannot make picks.")
        return redirect('entry_detail', entry_id=entry.id)
    
    # Get pool-specific settings for this week
    week_settings = PoolWeekSettings.objects.filter(pool=entry.pool, week=current_week).first()
    if not week_settings:
        messages.error(request, "Week settings not found for this pool.")
        return redirect('entry_detail', entry_id=entry.id)
    
    # Check if this is a double-pick week
    if week_settings.is_double:
        # Get existing picks for this week
        existing_picks = Pick.objects.filter(entry=entry, week=current_week)
        
        if request.method == 'POST':
            form = DoublePickForm(request.POST, entry=entry, week=current_week)
            
            if form.is_valid():
                # Delete existing picks for this week
                existing_picks.delete()
                
                # Save new picks
                picks = form.save()
                
                messages.success(request, f"Your picks for Week {current_week.number} have been saved.")
                return redirect('entry_detail', entry_id=entry.id)
        else:
            # If there are existing picks, pre-populate the form
            initial_data = {}
            if existing_picks.count() >= 2:
                initial_data = {
                    'team1': existing_picks[0].team,
                    'team2': existing_picks[1].team,
                }
            
            form = DoublePickForm(entry=entry, week=current_week, initial=initial_data)
    else:
        # Regular single-pick week
        # Try to get existing pick
        try:
            existing_pick = Pick.objects.get(entry=entry, week=current_week)
        except Pick.DoesNotExist:
            existing_pick = None
        
        if request.method == 'POST':
            # Handle the form submission
            if existing_pick:
                # If editing existing pick, use that instance
                form = PickForm(request.POST, instance=existing_pick, entry=entry, week=current_week)
            else:
                # If creating new pick, start from scratch but with entry and week set
                form = PickForm(request.POST, entry=entry, week=current_week)
            
            if form.is_valid():
                try:
                    # Get the team from the cleaned data
                    team = form.cleaned_data['team']
                    
                    # Delete any existing picks for this entry and week to avoid duplicates
                    Pick.objects.filter(entry=entry, week=current_week).delete()
                    
                    # For entries created by admin, we need to be very explicit
                    # First, delete any existing picks to avoid duplicates
                    Pick.objects.filter(entry=entry, week=current_week).delete()
                    
                    # Create a new pick directly instead of using form.save
                    # This ensures all fields are properly set
                    pick = Pick(
                        entry=entry,  # Explicitly set the entry
                        week=current_week,
                        team=team
                    )
                    pick.save()
                    
                    messages.success(request, f'Successfully saved your pick of {team} for Week {current_week.number}')
                    return redirect('entry_detail', entry_id=entry.id)
                except ValidationError as e:
                    messages.error(request, str(e))
            # Let the form handle displaying errors
            context = {
                'form': form,
                'entry': entry,
                'week': current_week,
                'is_double_pick': week_settings.is_double if week_settings else False,
            }
            return render(request, 'pool/make_pick.html', context)
        else:
            form = PickForm(instance=existing_pick, entry=entry, week=current_week)
    
    context = {
        'form': form,
        'entry': entry,
        'week': current_week,
        'is_double_pick': week_settings.is_double if week_settings else False,
    }
    
    return render(request, 'pool/make_pick.html', context)


@login_required
def quick_pick(request, pool_id):
    """
    View for making picks for multiple entries at once.
    """
    pool = get_object_or_404(Pool, id=pool_id)
    
    # Get user's entries in this pool
    user_entries = Entry.objects.filter(pool=pool, user=request.user, is_alive=True)
    
    if not user_entries.exists():
        messages.error(request, "You don't have any active entries in this pool.")
        return redirect('pool_detail', pool_id=pool.id)
    
    # Get current week
    current_week = Week.objects.filter(
        start_date__lte=timezone.now().date(),
        end_date__gte=timezone.now().date()
    ).first()
    
    # If no current week, get the next upcoming week
    if not current_week:
        current_week = Week.objects.filter(
            start_date__gt=timezone.now().date()
        ).order_by('start_date').first()
    
    # Check if deadline has passed
    if current_week.is_past_deadline():
        messages.error(request, f"The deadline for Week {current_week.number} has passed.")
        return redirect('pool_detail', pool_id=pool.id)
    
    if request.method == 'POST':
        form = QuickPickForm(
            request.POST,
            user=request.user,
            week=current_week,
            entries=user_entries
        )
        
        if form.is_valid():
            # Delete existing picks for this week
            for entry in user_entries:
                Pick.objects.filter(entry=entry, week=current_week).delete()
            
            # Save new picks
            picks = form.save()
            
            messages.success(request, f"Your picks for Week {current_week.number} have been saved.")
            return redirect('pool_detail', pool_id=pool.id)
    else:
        # Pre-populate form with existing picks
        initial_data = {}
        for entry in user_entries:
            existing_picks = Pick.objects.filter(entry=entry, week=current_week)
            
            if current_week.is_double:
                if existing_picks.count() >= 2:
                    initial_data[f'entry_{entry.id}_team1'] = existing_picks[0].team
                    initial_data[f'entry_{entry.id}_team2'] = existing_picks[1].team
            else:
                if existing_picks.exists():
                    initial_data[f'entry_{entry.id}_team'] = existing_picks.first().team
        
        form = QuickPickForm(
            user=request.user,
            week=current_week,
            entries=user_entries,
            initial=initial_data
        )
    
    context = {
        'form': form,
        'pool': pool,
        'week': current_week,
        'entries': user_entries,
        'is_double_pick': current_week.is_double,
    }
    
    return render(request, 'pool/quick_pick.html', context)


@login_required
def standings(request, pool_id):
    """
    View showing standings for a specific pool.
    """
    pool = get_object_or_404(Pool, id=pool_id)
    
    # Get all entries in this pool
    alive_entries = Entry.objects.filter(pool=pool, is_alive=True)
    eliminated_entries = Entry.objects.filter(pool=pool, is_alive=False)
    
    # Get current week
    current_week = Week.objects.filter(
        start_date__lte=timezone.now().date(),
        end_date__gte=timezone.now().date()
    ).first()
    
    # If no current week, get the next upcoming week
    if not current_week:
        current_week = Week.objects.filter(
            start_date__gt=timezone.now().date()
        ).order_by('start_date').first()
    
    # Get picks for the current week (only if deadline has passed)
    current_week_picks = None
    if current_week and current_week.is_past_deadline():
        current_week_picks = Pick.objects.filter(week=current_week, entry__pool=pool)
        
        # Count how many entries picked each team
        team_counts = current_week_picks.values('team').annotate(
            count=Count('entry', distinct=True)
        ).order_by('-count')
        
        # Get team objects for the counts
        teams_with_counts = []
        for item in team_counts:
            team = Team.objects.get(id=item['team'])
            teams_with_counts.append({
                'team': team,
                'count': item['count']
            })
    else:
        teams_with_counts = None
    
    context = {
        'pool': pool,
        'alive_entries': alive_entries,
        'eliminated_entries': eliminated_entries,
        'current_week': current_week,
        'current_week_picks': current_week_picks,
        'teams_with_counts': teams_with_counts,
    }
    
    return render(request, 'pool/standings.html', context)


@login_required
def week_picks(request, pool_id, week_number):
    """
    View showing all picks for a specific week in a pool.
    """
    pool = get_object_or_404(Pool, id=pool_id)
    week = get_object_or_404(Week, number=week_number)
    
    # Check if deadline has passed
    if not week.is_past_deadline():
        messages.error(request, f"Picks for Week {week.number} are not visible until after the deadline.")
        return redirect('pool_detail', pool_id=pool.id)
    
    # Get all picks for this week in this pool
    picks = Pick.objects.filter(week=week, entry__pool=pool)
    
    # Count how many entries picked each team
    team_counts = picks.values('team').annotate(
        count=Count('entry', distinct=True)
    ).order_by('-count')
    
    # Get team objects for the counts
    teams_with_counts = []
    for item in team_counts:
        team = Team.objects.get(id=item['team'])
        teams_with_counts.append({
            'team': team,
            'count': item['count']
        })
    
    context = {
        'pool': pool,
        'week': week,
        'picks': picks,
        'teams_with_counts': teams_with_counts,
        'is_double_pick': week.is_double,
    }
    
    return render(request, 'pool/week_picks.html', context)
