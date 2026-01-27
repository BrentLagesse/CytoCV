"""Forms for user signup and validation."""

from __future__ import annotations

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.validators import EmailValidator, ValidationError
from django.forms import models


class SignupForm(models.ModelForm):
    """Signup form with username, email, and password validation."""
    username = forms.CharField(widget=forms.TextInput)
    password = forms.CharField(widget=forms.PasswordInput)
    verify_password = forms.CharField(widget=forms.PasswordInput)
    email = forms.EmailField(
        widget=forms.EmailInput,
        validators=[EmailValidator(message="Enter a valid email address")],
    )
    verify_code = forms.CharField(widget=forms.TextInput, required=False)
    first_name = forms.CharField(max_length=20, widget=forms.TextInput)
    last_name = forms.CharField(max_length=20, widget=forms.TextInput)

    class Meta:
        model = get_user_model()
        fields = ["username", "email", "first_name", "last_name", "password", "verify_password"]

    def clean_username(self):
        """Ensure the username is unique."""
        UserModel = get_user_model()
        username = self.cleaned_data.get('username')
        if UserModel.objects.filter(username=username).exists():
            raise forms.ValidationError("Username already in use.")
        return username

    def clean_email(self):
        """Ensure the email is unique."""
        UserModel = get_user_model()
        email = self.cleaned_data.get('email')
        if UserModel.objects.filter(email=email).exists():
            raise forms.ValidationError("Email already in use.")
        return email

    def clean_password(self):
        """Validate password strength against the username."""
        UserModel = get_user_model()
        password = self.cleaned_data.get('password')
        username = self.cleaned_data.get('username')

        dummy = UserModel(username=username, password=password)

        try:
            validate_password(password, user=dummy)
        except ValidationError as e:
            raise forms.ValidationError(e)
        return password

    def clean_verify_password(self):
        """Ensure the verification password matches."""
        password = self.cleaned_data.get('password')
        verify_password = self.cleaned_data.get('verify_password')

        if password is not None and verify_password != password:
            raise forms.ValidationError("Passwords don't match.")
        return verify_password

    def save(self, commit=True):
        """Persist a user with a hashed password."""
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])

        if commit:
            user.save()
        else:
            return user
