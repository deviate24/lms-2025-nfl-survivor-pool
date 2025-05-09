from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q
from django.utils import timezone
from django.urls import reverse
from .models import Pool, Week, Team, Entry, Pick, PoolWeekSettings, WeeklyResult, AuditLog
from .forms import PickForm, QuickPickForm, DoublePickForm


@login_required
def home(request):
    """
    Home page view showing the user's pools and entries.
    """
    # Get all pools the user has entries in
    user_pools = Pool.objects.filter(entries__user=request.user).distinct()
    
    # Get current week
    current_week = Week.objects.filter(
        start_date__lte=timezone.now(),
        end_date__gte=timezone.now()
    ).first()
    
    # If no current week, get the next upcoming week
    if not current_week:
        current_week = Week.objects.filter(
            start_date__gt=timezone.now()
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
    
    # Process automatic eliminations for entries without picks after deadline
    eliminated_count = pool.process_missing_picks_eliminations()
    if eliminated_count > 0:
        messages.warning(request, f'{eliminated_count} entries were eliminated due to no picks by the deadline.')
    
    # Get user's entries in this pool
    user_entries = Entry.objects.filter(pool=pool, user=request.user)
    
    # Get current week
    current_week = Week.objects.filter(
        start_date__lte=timezone.now(),
        end_date__gte=timezone.now()
    ).first()
    
    # If no current week, get the next upcoming week
    if not current_week:
        current_week = Week.objects.filter(
            start_date__gt=timezone.now()
        ).order_by('start_date').first()
    
    # Get all entries in this pool
    all_entries = Entry.objects.filter(pool=pool)
    alive_entries = all_entries.filter(is_alive=True)
    eliminated_entries = all_entries.filter(is_alive=False)
    
    # Get the current picks for each of the user's entries
    # Sort entries so alive entries appear first, then eliminated entries
    alive_user_entries = user_entries.filter(is_alive=True)
    eliminated_user_entries = user_entries.filter(is_alive=False)
    
    # Combine the lists with alive entries first
    sorted_user_entries = list(alive_user_entries) + list(eliminated_user_entries)
    
    # Get picks for each entry in the sorted order
    entries_with_picks = []
    for entry in sorted_user_entries:
        # Get the current week's pick(s) for this entry
        picks = Pick.objects.filter(entry=entry, week=current_week).select_related('team')
        entry_data = {
            'entry': entry,
            'picks': picks,
            'has_pick': picks.exists()
        }
        entries_with_picks.append(entry_data)
    
    # Get the week settings to check if it's a double-pick week
    week_settings = None
    if current_week:
        week_settings = PoolWeekSettings.objects.filter(pool=pool, week=current_week).first()
    
    context = {
        'pool': pool,
        'entries_with_picks': entries_with_picks,
        'current_week': current_week,
        'alive_entries': alive_entries,
        'eliminated_entries': eliminated_entries,
        'is_double_pick': week_settings.is_double if week_settings else False,
    }
    
    return render(request, 'pool/pool_detail.html', context)


@login_required
def entry_detail(request, entry_id):
    """
    View showing details of a specific entry.
    Privacy controls applied for non-owners:
    - Only past week picks are visible to non-owners
    - Current week picks are hidden until deadline passes
    - Available teams are visible to anyone
    """
    entry = get_object_or_404(Entry, id=entry_id)
    
    # Determine if the user is the owner of this entry
    is_owner = (entry.user == request.user)
    
    # Get all picks for this entry
    picks = Pick.objects.filter(entry=entry).order_by('week__number')
    
    # Get current week
    current_week = Week.objects.filter(
        start_date__lte=timezone.now(),
        end_date__gte=timezone.now()
    ).first()
    
    # If no current week, get the next upcoming week
    if not current_week:
        current_week = Week.objects.filter(
            start_date__gt=timezone.now()
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
    
    # Apply privacy controls for non-owners
    if not is_owner:
        # For current week's picks, only show if past deadline
        if current_week and not current_week.is_past_deadline:
            current_week_picks = None
            has_current_pick = False  # Hide this information
        
        # Only show picks from past weeks to non-owners
        if current_week:
            picks = picks.filter(week__number__lt=current_week.number)
    
    context = {
        'entry': entry,
        'picks': picks,
        'current_week': current_week,
        'has_current_pick': has_current_pick,
        'current_week_picks': current_week_picks,
        'available_teams': available_teams,
        'is_double_pick': is_double_pick,
        'is_owner': is_owner,  # Pass ownership status to template
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
    today = timezone.now()
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
                # Get the selected teams from the form
                team1 = form.cleaned_data['team1']
                team2 = form.cleaned_data['team2']
                
                # Store old teams for audit logging
                old_team1 = None
                old_team2 = None
                if existing_picks.count() >= 2:
                    old_team1 = existing_picks[0].team
                    old_team2 = existing_picks[1].team
                
                # Delete existing picks for this week
                existing_picks.delete()
                
                # Save new picks
                picks = form.save()
                
                # Create audit log entries
                if old_team1 and old_team2:
                    # Log a change of picks
                    action = "DOUBLE_PICK_CHANGED"
                    details = f"{entry.entry_name} changed picks for Week {current_week.number} from {old_team1}/{old_team2} to {team1}/{team2}"
                    AuditLog.create(request.user, action, entry, current_week, details)
                else:
                    # Log new picks
                    action = "DOUBLE_PICK_CREATED"
                    details = f"{entry.entry_name} picked {team1} and {team2} for Week {current_week.number}"
                    AuditLog.create(request.user, action, entry, current_week, details)
                
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
                    
                    # Check for existing pick to determine if this is a new pick or a change
                    existing_pick = Pick.objects.filter(entry=entry, week=current_week).first()
                    
                    # Store the old team for the audit log if this is a change
                    old_team = None
                    if existing_pick:
                        old_team = existing_pick.team
                    
                    # Delete any existing picks for this entry and week to avoid duplicates
                    Pick.objects.filter(entry=entry, week=current_week).delete()
                    
                    # Create a new pick directly instead of using form.save
                    # This ensures all fields are properly set
                    pick = Pick(
                        entry=entry,  # Explicitly set the entry
                        week=current_week,
                        team=team
                    )
                    pick.save()
                    
                    # Create audit log entry
                    if old_team:
                        # Log a pick change
                        action = "PICK_CHANGED"
                        details = f"{entry.entry_name} changed pick for Week {current_week.number} from {old_team} to {team}"
                        AuditLog.create(request.user, action, entry, current_week, details)
                    else:
                        # Log a new pick
                        action = "PICK_CREATED"
                        details = f"{entry.entry_name} picked {team} for Week {current_week.number}"
                        AuditLog.create(request.user, action, entry, current_week, details)
                    
                    messages.success(request, f'Successfully saved your pick of {team} for Week {current_week.number}')
                    return redirect('pool_detail', pool_id=entry.pool.id)
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
            # Explicitly set the initial team value to the existing pick's team
            initial_data = {}
            if existing_pick and existing_pick.team:
                initial_data = {'team': existing_pick.team}
            form = PickForm(instance=existing_pick, entry=entry, week=current_week, initial=initial_data)
    
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
        start_date__lte=timezone.now(),
        end_date__gte=timezone.now()
    ).first()
    
    # If no current week, get the next upcoming week
    if not current_week:
        current_week = Week.objects.filter(
            start_date__gt=timezone.now()
        ).order_by('start_date').first()
    
    # Check if deadline has passed
    if current_week.is_past_deadline():
        messages.error(request, f"The deadline for Week {current_week.number} has passed.")
        return redirect('pool_detail', pool_id=pool.id)
    
    # Get week settings to check if this is a double-pick week
    week_settings = PoolWeekSettings.objects.filter(pool=pool, week=current_week).first()
    is_double_pick = week_settings.is_double if week_settings else False
    
    if request.method == 'POST':
        form = QuickPickForm(
            request.POST,
            user=request.user,
            week=current_week,
            entries=user_entries,
            is_double_pick=is_double_pick
        )
        
        if form.is_valid():
            # Store existing picks for audit logging
            existing_picks_map = {}
            for entry in user_entries:
                entry_picks = list(Pick.objects.filter(entry=entry, week=current_week))
                existing_picks_map[entry.id] = entry_picks
            
            # Delete existing picks for this week
            for entry in user_entries:
                Pick.objects.filter(entry=entry, week=current_week).delete()
            
            # Save new picks
            picks = form.save()
            
            # Create audit log entries for each entry
            for entry in user_entries:
                if is_double_pick:
                    team1_field = f'entry_{entry.id}_team1'
                    team2_field = f'entry_{entry.id}_team2'
                    
                    if team1_field in form.cleaned_data and team2_field in form.cleaned_data:
                        team1 = form.cleaned_data[team1_field]
                        team2 = form.cleaned_data[team2_field]
                        
                        # Get old teams for comparison
                        old_teams = [p.team for p in existing_picks_map.get(entry.id, [])]
                        old_teams_str = ", ".join([t.name for t in old_teams]) if old_teams else "None"
                        
                        # Create audit entry
                        if old_teams:
                            action = "Changed Pick"
                            details = f"Changed from {old_teams_str} to {team1.name}, {team2.name} via Quick Pick"
                        else:
                            action = "Made Pick"
                            details = f"Selected {team1.name}, {team2.name} via Quick Pick"
                        
                        AuditLog.create(request.user, action, entry, current_week, details)
                else:
                    team_field = f'entry_{entry.id}_team'
                    
                    if team_field in form.cleaned_data:
                        team = form.cleaned_data[team_field]
                        
                        # Get old team for comparison
                        old_teams = [p.team for p in existing_picks_map.get(entry.id, [])]
                        old_team_str = old_teams[0].name if old_teams else "None"
                        
                        # Create audit entry
                        if old_teams:
                            action = "Changed Pick"
                            details = f"Changed from {old_team_str} to {team.name} via Quick Pick"
                        else:
                            action = "Made Pick"
                            details = f"Selected {team.name} via Quick Pick"
                        
                        AuditLog.create(request.user, action, entry, current_week, details)
            
            messages.success(request, f"Your picks for Week {current_week.number} have been saved.")
            return redirect('pool_detail', pool_id=pool.id)
    else:
        # Pre-populate form with existing picks
        initial_data = {}
        
        for entry in user_entries:
            existing_picks = Pick.objects.filter(entry=entry, week=current_week)
            
            if is_double_pick:
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
            is_double_pick=is_double_pick,
            initial=initial_data
        )
    
    context = {
        'form': form,
        'pool': pool,
        'week': current_week,
        'entries': user_entries,
        'is_double_pick': is_double_pick,
    }
    
    return render(request, 'pool/quick_pick.html', context)


@login_required
def standings(request, pool_id):
    """
    View showing standings for a specific pool.
    """
    pool = get_object_or_404(Pool, id=pool_id)
    
    # Process automatic eliminations for entries without picks after deadline
    eliminated_count = pool.process_missing_picks_eliminations()
    if eliminated_count > 0:
        messages.warning(request, f'{eliminated_count} entries were eliminated due to no picks by the deadline.')
    
    # Get all entries in this pool
    alive_entries = Entry.objects.filter(pool=pool, is_alive=True)
    
    # Apply sorting to eliminated entries if requested
    sort = request.GET.get('sort')
    order = request.GET.get('order')
    
    eliminated_entries = Entry.objects.filter(pool=pool, is_alive=False)
    
    if sort == 'entry_name':
        # Sort by entry name
        if order == 'desc':
            eliminated_entries = eliminated_entries.order_by('-entry_name')
        else:
            eliminated_entries = eliminated_entries.order_by('entry_name')
    elif sort == 'eliminated_week':
        # Sort by elimination week
        if order == 'desc':
            eliminated_entries = eliminated_entries.order_by('-eliminated_in_week__number')
        else:
            eliminated_entries = eliminated_entries.order_by('eliminated_in_week__number')
    
    # Get current week
    current_week = Week.objects.filter(
        start_date__lte=timezone.now(),
        end_date__gte=timezone.now()
    ).first()
    
    # If no current week, get the next upcoming week
    if not current_week:
        current_week = Week.objects.filter(
            start_date__gt=timezone.now()
        ).order_by('start_date').first()
    
    # Get picks for the current week and previous week
    current_week_picks = None
    teams_with_counts = None
    previous_week = None
    previous_week_picks = None
    previous_teams_with_counts = None
    user_entries_ids = []
    
    # Get the user's entries IDs for this pool
    if request.user.is_authenticated:
        user_entries_ids = Entry.objects.filter(pool=pool, user=request.user).values_list('id', flat=True)
    
    if current_week:
        # Try to get the previous week
        if current_week.number > 1:
            previous_week = Week.objects.filter(number=current_week.number-1).first()
        
        if current_week.is_past_deadline():
            # If deadline has passed, show all picks for current week
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
                
            # Get only alive entries or entries that were eliminated in the current week
            # (they should have made a pick but didn't)
            eligible_entries = Entry.objects.filter(pool=pool).filter(Q(is_alive=True) | Q(eliminated_in_week=current_week)).count()
            
            # Get number of entries that made picks for this week
            entries_with_picks = Pick.objects.filter(week=current_week, entry__pool=pool).values('entry').distinct().count()
            
            # Calculate eligible entries with no picks
            no_pick_count = eligible_entries - entries_with_picks
            
            # Add No Pick to the distribution if there are entries without picks
            if no_pick_count > 0:
                teams_with_counts.append({
                    'team': None,  # No team selected
                    'count': no_pick_count,
                    'is_no_pick': True  # Flag to identify this as No Pick in template
                })
            
            # Process previous week data if available
            if previous_week:
                # Get previous week picks
                previous_week_picks = Pick.objects.filter(week=previous_week, entry__pool=pool)
                
                # Count how many entries picked each team in previous week
                prev_team_counts = previous_week_picks.values('team').annotate(
                    count=Count('entry', distinct=True)
                ).order_by('-count')
                
                # Get team objects for the counts
                previous_teams_with_counts = []
                for item in prev_team_counts:
                    team = Team.objects.get(id=item['team'])
                    previous_teams_with_counts.append({
                        'team': team,
                        'count': item['count']
                    })
                
                # Calculate no picks for previous week - only include entries that were alive at that time
                # (either still alive or eliminated in this/later weeks)
                prev_eligible_entries = Entry.objects.filter(pool=pool).filter(
                    Q(is_alive=True) | 
                    Q(eliminated_in_week__number__gte=previous_week.number)
                ).count()
                
                prev_entries_with_picks = Pick.objects.filter(week=previous_week, entry__pool=pool).values('entry').distinct().count()
                prev_no_pick_count = prev_eligible_entries - prev_entries_with_picks
                
                if prev_no_pick_count > 0:
                    previous_teams_with_counts.append({
                        'team': None,
                        'count': prev_no_pick_count,
                        'is_no_pick': True
                    })
        else:
            # If deadline has not passed, only show user's picks
            if user_entries_ids:
                current_week_picks = Pick.objects.filter(week=current_week, entry__id__in=user_entries_ids)
                # Don't show team distribution before deadline
                
            # But still show previous week distribution if available
            if previous_week and previous_week.is_past_deadline():
                # Get previous week picks
                previous_week_picks = Pick.objects.filter(week=previous_week, entry__pool=pool)
                
                # Count how many entries picked each team in previous week
                prev_team_counts = previous_week_picks.values('team').annotate(
                    count=Count('entry', distinct=True)
                ).order_by('-count')
                
                # Get team objects for the counts
                previous_teams_with_counts = []
                for item in prev_team_counts:
                    team = Team.objects.get(id=item['team'])
                    previous_teams_with_counts.append({
                        'team': team,
                        'count': item['count']
                    })
                
                # Calculate no picks for previous week
                total_entries = Entry.objects.filter(pool=pool).count()
                prev_entries_with_picks = Pick.objects.filter(week=previous_week, entry__pool=pool).values('entry').distinct().count()
                prev_no_pick_count = total_entries - prev_entries_with_picks
                
                if prev_no_pick_count > 0:
                    previous_teams_with_counts.append({
                        'team': None,
                        'count': prev_no_pick_count,
                        'is_no_pick': True
                    })
    
    context = {
        'pool': pool,
        'alive_entries': alive_entries,
        'eliminated_entries': eliminated_entries,
        'current_week': current_week,
        'current_week_picks': current_week_picks,
        'teams_with_counts': teams_with_counts,
        'previous_week': previous_week,
        'previous_week_picks': previous_week_picks,
        'previous_teams_with_counts': previous_teams_with_counts,
        'current_tab': request.GET.get('tab', 'alive'),
    }
    
    return render(request, 'pool/standings.html', context)


def rules(request):
    """
    View for displaying the NFL Survivor Pool rules.
    """
    return render(request, 'pool/rules.html')


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
    
    # Check if this is a double pick week for this pool
    week_settings = PoolWeekSettings.objects.filter(pool=pool, week=week).first()
    is_double_pick = week_settings.is_double if week_settings else False
    
    context = {
        'pool': pool,
        'week': week,
        'picks': picks,
        'teams_with_counts': teams_with_counts,
        'is_double_pick': is_double_pick,
    }
    
    return render(request, 'pool/week_picks.html', context)
