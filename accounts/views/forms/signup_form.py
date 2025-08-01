from django import forms
from django.contrib.auth import get_user_model
from django.core.validators import EmailValidator, ValidationError
from django.contrib.auth.password_validation import validate_password
from django.forms import models


class SignupForm(models.ModelForm):
    username = forms.CharField(widget=forms.TextInput)
    password = forms.CharField(widget=forms.PasswordInput)
    verify_password = forms.CharField(widget=forms.PasswordInput)
    email = forms.EmailField(widget=forms.EmailInput,validators=[EmailValidator(message="Enter a valid email address")])
    verify_code = forms.CharField(widget=forms.TextInput, required=False)
    first_name = forms.CharField(max_length=20, widget=forms.TextInput)
    last_name = forms.CharField(max_length=20, widget=forms.TextInput)

    class Meta:
        model = get_user_model()
        # include all listed field above in the form because of ModelForm required
        fields = ['username', 'email', 'first_name', 'last_name','password','verify_password']

    def clean_username(self):
        UserModel = get_user_model()
        # check if username already existed
        username = self.cleaned_data.get('username')
        if UserModel.objects.filter(username=username).exists():
            raise forms.ValidationError("Username already in use.")
        return username

    def clean_email(self):
        UserModel = get_user_model()
        # check if email already associated with another account
        email = self.cleaned_data.get('email')
        if UserModel.objects.filter(email=email).exists():
            raise forms.ValidationError("Email already in use.")
        return email

    def clean_password(self):
        UserModel = get_user_model()
        # check for password and username similarity
        password = self.cleaned_data.get('password')
        username = self.cleaned_data.get('username')

        dummy = UserModel(username=username,password=password) # this is just to check for similarity

        try:
            validate_password(password,user=dummy)
        except ValidationError as e:
            raise forms.ValidationError(e)
        return password

    def clean_verify_password(self):
        password = self.cleaned_data.get('password')
        verify_password = self.cleaned_data.get('verify_password')

        if password is not None and verify_password != password:
            raise forms.ValidationError("Passwords don't match.")
        return verify_password

    def save(self, commit=True):
        user = super().save(commit=False)
        # Save the provided password in hashed format
        user.set_password(self.cleaned_data['password'])

        if commit:
            user.save()
        else:
            return user
