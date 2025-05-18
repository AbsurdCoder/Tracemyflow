# authentication/views.py

from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import reverse_lazy
from .forms import CustomUserCreationForm, CustomAuthenticationForm
from .models import UserProfile
import logging
logger = logging.getLogger(__name__)

class CustomLoginView(LoginView):
    form_class = CustomAuthenticationForm
    template_name = 'authentication/login.html'
    
    def get_success_url(self):
        return reverse_lazy('workflow:list')

class CustomLogoutView(LogoutView):
    next_page = reverse_lazy('home')

def register_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            raw_password = form.cleaned_data.get('password1')
            user = authenticate(username=user.username, password=raw_password)
            login(request, user)
            return redirect('workflow:list')
    else:
        form = CustomUserCreationForm()
    return render(request, 'authentication/register.html', {'form': form})

@login_required
def profile_view(request):
    user_profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        user_profile.department = request.POST.get('department', '')
        user_profile.role = request.POST.get('role', '')
        user_profile.save()
        return redirect('authentication:profile')
        
    return render(request, 'authentication/profile.html', {'profile': user_profile})