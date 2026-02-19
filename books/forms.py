from django import forms
from .models import UserBook


class UserBookForm(forms.ModelForm):
    class Meta:
        model = UserBook
        fields = ["status", "rating", "notes"]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get("status")
        rating = cleaned_data.get("rating")
        notes = cleaned_data.get("notes")

        # Validation for Rating
        if rating and status != "read":
            self.add_error("rating", "You can only rate books that you have read.")

        # Validation for Notes
        if notes and status not in ["reading", "read"]:
            self.add_error(
                "notes", "You can only add notes to books you are reading or have read."
            )

        return cleaned_data
