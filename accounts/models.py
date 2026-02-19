from django.db import models
from django.contrib.auth.models import User


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    favorite_genres = models.CharField(
        max_length=255, blank=True, help_text="Comma-separated, e.g. Sci-Fi,Fantasy"
    )
    reading_goal = models.IntegerField(default=12, help_text="Books per year")
    bio = models.TextField(blank=True)

    def __str__(self):
        return f"{self.user.username}'s profile"
