from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.utils.html import format_html
from .models import Pick, Team, Week, AuditLog

@staff_member_required
def admin_edit_pick(request, pick_id):
    """
    Special admin view to edit picks directly, bypassing all validation checks.
    This allows administrators to correct picks even after deadlines have passed.
    """
    # Only superusers can access this
    if not request.user.is_superuser:
        return HttpResponseForbidden("Only superadmins can edit picks directly.")
        
    # Get the pick
    pick = get_object_or_404(Pick, id=pick_id)
    teams = Team.objects.all().order_by('conference', 'division', 'city')
    
    if request.method == 'POST':
        # Get form data
        team_id = request.POST.get('team')
        result = request.POST.get('result')
        
        if team_id and result:
            # Record original values for logging
            old_team = pick.team
            old_result = pick.result
            
            # Update the pick directly - bypass ALL validation
            team = get_object_or_404(Team, id=team_id)
            pick.team = team
            pick.result = result
            
            # Save without validation
            Pick.objects.filter(id=pick.id).update(team=team, result=result)
            
            # Create audit log
            changes = []
            if old_team != team:
                changes.append(f"team from {old_team} to {team}")
            if old_result != result:
                changes.append(f"result from {old_result} to {result}")
                
            if changes:
                changes_text = " and ".join(changes)
                AuditLog.create(
                    user=request.user,
                    action="ADMIN_DIRECT_EDIT_PICK",
                    entry=pick.entry,
                    week=pick.week,
                    details=f"Administrator {request.user.username} directly edited pick {changes_text}."
                )
                
                # Update entry status if result changed
                if old_result != result and (old_result == 'win' or result == 'win') and (old_result == 'loss' or result == 'loss'):
                    # Handle entry elimination/revival based on the new result
                    process_entry_status_change(request, pick, old_result, result)
            
            # Redirect back to the entry detail page with success message
            messages.success(request, format_html(
                "Successfully updated pick from {} / {} to {} / {}",
                old_team, old_result, team, result
            ))
            return redirect(f'/admin/pool/entry/{pick.entry.id}/change/')
            
    # Prepare context for the form
    context = {
        'pick': pick,
        'teams': teams,
        'result_choices': Pick._meta.get_field('result').choices,
        'title': f'Edit Pick for {pick.entry.entry_name} - Week {pick.week.number}'
    }
    
    return render(request, 'admin/pool/admin_edit_pick.html', context)

def process_entry_status_change(request, pick, old_result, new_result):
    """Helper function to update entry status based on pick result changes"""
    from .models import PoolWeekSettings, Entry
    from django.db.models import Count
    
    # Skip processing if both old and new are the same type (win/loss)
    if (old_result == 'win' and new_result == 'win') or \
       (old_result in ['loss', 'tie'] and new_result in ['loss', 'tie']):
        return
    
    # Check if double-pick week
    pool_settings = PoolWeekSettings.objects.filter(
        pool=pick.entry.pool, 
        week=pick.week
    ).first()
    is_double_pick = pool_settings and pool_settings.is_double
    
    if is_double_pick:
        # For double-pick weeks, we need to check all picks for this entry
        all_picks = Pick.objects.filter(entry=pick.entry, week=pick.week)
        
        # Count how many are wins
        win_count = all_picks.filter(result='win').count()
        loss_count = all_picks.filter(result__in=['loss', 'tie']).count()
        
        # If two picks and both are losses, eliminate
        if all_picks.count() == 2 and loss_count == 2 and pick.entry.is_alive:
            pick.entry.is_alive = False
            pick.entry.eliminated_in_week = pick.week
            pick.entry.save(update_fields=['is_alive', 'eliminated_in_week'])
            
            AuditLog.create(
                user=request.user,
                action="ADMIN_PICK_CHANGE_ELIMINATED",
                entry=pick.entry,
                week=pick.week,
                details=f"Entry was eliminated due to admin changing pick result to loss/tie."
            )
        # If was eliminated but now has at least one win, potentially revive
        elif win_count > 0 and not pick.entry.is_alive and pick.entry.eliminated_in_week == pick.week:
            # Check if any entry has 2 wins for this week
            entries_with_two_wins = Entry.objects.filter(
                pool=pick.entry.pool,
                picks__week=pick.week,
                picks__result='win'
            ).annotate(win_count=Count('picks')).filter(win_count=2)
            
            # If no entries with two wins, or this entry has two wins, revive it
            if not entries_with_two_wins.exists() or (win_count == 2):
                pick.entry.is_alive = True
                pick.entry.eliminated_in_week = None
                pick.entry.save(update_fields=['is_alive', 'eliminated_in_week'])
                
                AuditLog.create(
                    user=request.user,
                    action="ADMIN_PICK_CHANGE_REVIVED",
                    entry=pick.entry,
                    week=pick.week,
                    details=f"Entry was revived due to admin changing pick result to win."
                )
    else:
        # For regular weeks, it's simpler
        if new_result in ['loss', 'tie'] and pick.entry.is_alive:
            pick.entry.is_alive = False
            pick.entry.eliminated_in_week = pick.week
            pick.entry.save(update_fields=['is_alive', 'eliminated_in_week'])
            
            AuditLog.create(
                user=request.user,
                action="ADMIN_PICK_CHANGE_ELIMINATED",
                entry=pick.entry,
                week=pick.week,
                details=f"Entry was eliminated due to admin changing pick result to {new_result}."
            )
        elif new_result == 'win' and not pick.entry.is_alive and pick.entry.eliminated_in_week == pick.week:
            pick.entry.is_alive = True
            pick.entry.eliminated_in_week = None
            pick.entry.save(update_fields=['is_alive', 'eliminated_in_week'])
            
            AuditLog.create(
                user=request.user,
                action="ADMIN_PICK_CHANGE_REVIVED",
                entry=pick.entry,
                week=pick.week,
                details=f"Entry was revived due to admin changing pick result to win."
            )
