import uuid
from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError


class EmailSignUpForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("email",)

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if User.objects.filter(email=email).exists():
            raise ValidationError("A user with this email already exists.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        # Generate a unique username
        username_base = user.email.split("@")[0][:20]  # Limit base length
        unique_suffix = str(uuid.uuid4())[:8]
        user.username = f"{username_base}_{unique_suffix}"

        if commit:
            user.save()
        return user
