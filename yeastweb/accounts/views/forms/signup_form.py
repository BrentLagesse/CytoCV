"""Forms for user signup and validation.

Notes:
    - Keep validation server-side to avoid trusting client input.
    - Use Django's built-in validators for consistent error handling.
"""

from __future__ import annotations

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.validators import EmailValidator, RegexValidator, ValidationError
from django.forms import models


class SignupForm(models.ModelForm):
    """Signup form with username, email, and password validation.

    This form centralizes validation so all checks run server-side, even if
    the UI performs client-side hints. Do not rely on client validation alone.
    """
    username = forms.CharField(widget=forms.TextInput(attrs={"autocomplete": "username"}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))
    verify_password = forms.CharField(widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={"autocomplete": "email"}),
        validators=[EmailValidator(message="Enter a valid email address")],
    )
    verify_code = forms.CharField(
        max_length=6,
        required=False,
        widget=forms.TextInput(
            attrs={
                "inputmode": "numeric",
                "autocomplete": "one-time-code",
                "pattern": "[0-9]{6}",
                "maxlength": "6",
            }
        ),
        validators=[RegexValidator(r"^\d{6}$", "Enter the 6-digit code.")],
        help_text="Enter the 6-digit code sent to your email.",
    )
    first_name = forms.CharField(max_length=20, widget=forms.TextInput(attrs={"autocomplete": "given-name"}))
    last_name = forms.CharField(max_length=20, widget=forms.TextInput(attrs={"autocomplete": "family-name"}))

    class Meta:
        model = get_user_model()
        fields = ["username", "email", "first_name", "last_name", "password", "verify_password"]

    def clean_username(self) -> str:
        """Ensure the username is unique (case-sensitive by default)."""
        UserModel = get_user_model()
        username = self.cleaned_data.get('username')
        # Validate uniqueness to prevent duplicate accounts.
        if UserModel.objects.filter(username=username).exists():
            raise forms.ValidationError("Username already in use.")
        return username

    def clean_email(self) -> str:
        """Ensure the email is unique."""
        UserModel = get_user_model()
        email = self.cleaned_data.get('email')
        # Validate uniqueness for email-based login flows.
        if UserModel.objects.filter(email=email).exists():
            raise forms.ValidationError("Email already in use.")
        return email

    def clean_password(self) -> str:
        """Validate password strength against the username."""
        UserModel = get_user_model()
        password = self.cleaned_data.get('password')
        username = self.cleaned_data.get('username')

        # Use a lightweight user instance for password validation context.
        dummy = UserModel(username=username, password=password)

        try:
            validate_password(password, user=dummy)
        except ValidationError as e:
            # Preserve validator messages for clarity.
            raise forms.ValidationError(e)
        return password

    def clean_verify_password(self) -> str:
        """Ensure the verification password matches."""
        password = self.cleaned_data.get('password')
        verify_password = self.cleaned_data.get('verify_password')

        # Match both passwords to avoid account creation with typos.
        if password is not None and verify_password != password:
            raise forms.ValidationError("Passwords don't match.")
        return verify_password

    def save(self, commit: bool = True):
        """Persist a user with a hashed password."""
        user = super().save(commit=False)
        # Hash the password before storing it in the database.
        user.set_password(self.cleaned_data['password'])

        if commit:
            user.save()
        else:
            return user
