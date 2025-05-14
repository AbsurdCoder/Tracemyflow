# authentication/models.py

from django.db import models
from django.contrib.auth.models import User

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    department = models.CharField(max_length=100, blank=True)
    role = models.CharField(max_length=100, blank=True)
    is_workflow_admin = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.user.username}'s profile"