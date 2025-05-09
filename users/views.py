from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .forms import UserRegisterForm, UserUpdateForm, ProfileUpdateForm


def register(request):
    """
    User registration view.
    """
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            messages.success(request, f'Account created for {username}! You can now log in.')
            return redirect('login')
    else:
        form = UserRegisterForm()
    
    return render(request, 'users/register.html', {'form': form})


@login_required
def profile(request):
    """
    User profile view for updating account information.
    """
    if request.method == 'POST':
        u_form = UserUpdateForm(instance=request.user)  # Always read-only, not from POST
        p_form = ProfileUpdateForm(request.POST, instance=request.user.profile)
        
        if p_form.is_valid():
            # Only save profile preferences, username/email are read-only
            p_form.save()
            messages.success(request, 'Your preferences have been updated!')
            return redirect('profile')
    else:
        u_form = UserUpdateForm(instance=request.user)
        p_form = ProfileUpdateForm(instance=request.user.profile)
    
    context = {
        'u_form': u_form,
        'p_form': p_form,
    }
    
    return render(request, 'users/profile.html', context)
