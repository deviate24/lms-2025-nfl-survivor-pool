from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import Pick, Entry, Team


class PickForm(forms.ModelForm):
    """
    Form for submitting a pick for a specific entry and week.
    """
    class Meta:
        model = Pick
        fields = ['team']
        
    def __init__(self, *args, **kwargs):
        # Get entry and week from kwargs
        self.entry = kwargs.pop('entry', None)
        self.week = kwargs.pop('week', None)
        
        super().__init__(*args, **kwargs)
        
        if self.entry and self.week:
            # Get available teams for this entry
            available_teams = self.entry.get_available_teams(self.week)
            
            # Update the team field to only show available teams
            self.fields['team'].queryset = available_teams
            self.fields['team'].label = f"Select your team for Week {self.week.number}"
            self.fields['team'].widget.attrs.update({
                'class': 'form-select',
                'aria-label': 'Select team',
            })
    
    def clean(self):
        cleaned_data = super().clean()
        team = cleaned_data.get('team')
        
        if self.week and self.week.is_past_deadline():
            raise ValidationError("The deadline for this week has passed.")
        
        if self.entry and not self.entry.is_alive:
            raise ValidationError("This entry has been eliminated and cannot make picks.")
        
        if team and self.entry and not self.week.reset_pool:
            # Check if team was already used by this entry
            used_teams = self.entry.get_used_teams()
            if team in used_teams and not self.instance.pk:
                raise ValidationError(f"You have already used {team} in a previous week.")
        
        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Always set these fields, they're required for a valid Pick
        if self.entry:
            instance.entry = self.entry
        else:
            raise ValueError("Entry must be provided to save a Pick")
            
        if self.week:
            instance.week = self.week
        else:
            raise ValueError("Week must be provided to save a Pick")
        
        if commit:
            instance.save()
        
        return instance


class DoublePickForm(forms.Form):
    """
    Form for submitting two picks for a double-pick week.
    """
    team1 = forms.ModelChoiceField(
        queryset=Team.objects.none(),
        label="Pick 1",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    team2 = forms.ModelChoiceField(
        queryset=Team.objects.none(),
        label="Pick 2",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    def __init__(self, *args, **kwargs):
        self.entry = kwargs.pop('entry', None)
        self.week = kwargs.pop('week', None)
        
        super().__init__(*args, **kwargs)
        
        if self.entry and self.week:
            # Get available teams for this entry
            available_teams = self.entry.get_available_teams(self.week)
            
            # Update both team fields to show available teams
            self.fields['team1'].queryset = available_teams
            self.fields['team2'].queryset = available_teams
            
            # Set labels
            self.fields['team1'].label = f"Pick 1 for Week {self.week.number}"
            self.fields['team2'].label = f"Pick 2 for Week {self.week.number}"
    
    def clean(self):
        cleaned_data = super().clean()
        team1 = cleaned_data.get('team1')
        team2 = cleaned_data.get('team2')
        
        if self.week and self.week.is_past_deadline():
            raise ValidationError("The deadline for this week has passed.")
        
        if self.entry and not self.entry.is_alive:
            raise ValidationError("This entry has been eliminated and cannot make picks.")
        
        if team1 and team2 and team1 == team2:
            raise ValidationError("You must select two different teams.")
        
        return cleaned_data
    
    def save(self):
        """
        Create two Pick objects for the double-pick week.
        """
        if not self.is_valid():
            return None
        
        team1 = self.cleaned_data['team1']
        team2 = self.cleaned_data['team2']
        
        # Create first pick
        pick1 = Pick(
            entry=self.entry,
            week=self.week,
            team=team1
        )
        pick1.save()
        
        # Create second pick
        pick2 = Pick(
            entry=self.entry,
            week=self.week,
            team=team2
        )
        pick2.save()
        
        return [pick1, pick2]


class QuickPickForm(forms.Form):
    """
    Form for making picks for multiple entries at once.
    """
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.week = kwargs.pop('week', None)
        self.entries = kwargs.pop('entries', None)
        
        super().__init__(*args, **kwargs)
        
        if self.entries and self.week:
            # Create a field for each entry
            for entry in self.entries:
                available_teams = entry.get_available_teams(self.week)
                
                if self.week.is_double:
                    # For double-pick weeks, create two fields per entry
                    self.fields[f'entry_{entry.id}_team1'] = forms.ModelChoiceField(
                        queryset=available_teams,
                        label=f"{entry.entry_name} - Pick 1",
                        required=True,
                        widget=forms.Select(attrs={'class': 'form-select'})
                    )
                    self.fields[f'entry_{entry.id}_team2'] = forms.ModelChoiceField(
                        queryset=available_teams,
                        label=f"{entry.entry_name} - Pick 2",
                        required=True,
                        widget=forms.Select(attrs={'class': 'form-select'})
                    )
                else:
                    # For regular weeks, create one field per entry
                    self.fields[f'entry_{entry.id}_team'] = forms.ModelChoiceField(
                        queryset=available_teams,
                        label=f"{entry.entry_name}",
                        required=True,
                        widget=forms.Select(attrs={'class': 'form-select'})
                    )
    
    def clean(self):
        cleaned_data = super().clean()
        
        if self.week and self.week.is_past_deadline():
            raise ValidationError("The deadline for this week has passed.")
        
        # For double-pick weeks, ensure picks are different for each entry
        if self.week and self.week.is_double:
            for entry in self.entries:
                team1_key = f'entry_{entry.id}_team1'
                team2_key = f'entry_{entry.id}_team2'
                
                team1 = cleaned_data.get(team1_key)
                team2 = cleaned_data.get(team2_key)
                
                if team1 and team2 and team1 == team2:
                    raise ValidationError(f"You must select two different teams for {entry.entry_name}.")
        
        return cleaned_data
    
    def save(self):
        """
        Create Pick objects for all entries.
        """
        if not self.is_valid():
            return None
        
        picks = []
        
        for entry in self.entries:
            if self.week.is_double:
                # Handle double-pick week
                team1 = self.cleaned_data[f'entry_{entry.id}_team1']
                team2 = self.cleaned_data[f'entry_{entry.id}_team2']
                
                # Create first pick
                pick1 = Pick(
                    entry=entry,
                    week=self.week,
                    team=team1
                )
                pick1.save()
                picks.append(pick1)
                
                # Create second pick
                pick2 = Pick(
                    entry=entry,
                    week=self.week,
                    team=team2
                )
                pick2.save()
                picks.append(pick2)
            else:
                # Handle regular week
                team = self.cleaned_data[f'entry_{entry.id}_team']
                
                pick = Pick(
                    entry=entry,
                    week=self.week,
                    team=team
                )
                pick.save()
                picks.append(pick)
        
        return picks
