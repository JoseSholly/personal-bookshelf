from django import forms
from .models import UserBook

FIELD_CLASS = (
    "block w-full rounded-md border-0 py-1.5 px-3 text-gray-900 shadow-sm "
    "ring-1 ring-inset ring-gray-300 placeholder:text-gray-400 focus:ring-2 "
    "focus:ring-inset focus:ring-accent-600 sm:text-sm sm:leading-6"
)


class UserBookForm(forms.ModelForm):
    class Meta:
        model = UserBook
        fields = ["status", "rating", "notes"]
        widgets = {
            "status": forms.Select(attrs={"class": FIELD_CLASS}),
            "notes": forms.Textarea(attrs={"rows": 3, "class": FIELD_CLASS}),
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
