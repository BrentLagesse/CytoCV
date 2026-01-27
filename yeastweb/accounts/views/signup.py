"""Signup view with email verification code flow."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.core.mail import send_mail
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.template.response import TemplateResponse

from .forms import SignupForm

def signup(request: HttpRequest) -> HttpResponse:
    """Handle signup form submission and email verification."""
    verify_code = request.session.get('verify_code', None)
    if request.method == 'POST':
        form = SignupForm(request.POST)
        if form.is_valid():
            if 'submit' in request.POST:
                print(verify_code)
                code = form.cleaned_data['verify_code']
                if not code:
                    return TemplateResponse(
                        request,
                        "registration/signup.html",
                        {"form": form, "error": "Please enter a verification code"},
                    )
                else:
                    if not verify_code:
                        return TemplateResponse(
                            request,
                            "registration/signup.html",
                            {"form": form, "error": "Please send a verification code"},
                        )
                    if code == verify_code:
                        form.save()
                        return redirect('login')

            if 'send_code' in request.POST:
                verify_code = str(uuid.uuid4())
                request.session['verify_code'] = verify_code  # Store the verify_code in session

                message = "Your verification code is {}".format(verify_code)
                email = form.cleaned_data.get('email')

                send_mail(
                    "Yeast Analysis Tools verification code",
                    message,
                    settings.EMAIL_HOST_USER,
                    [email],
                    fail_silently=False,
                )
            return TemplateResponse(
                request,
                "registration/signup.html",
                {"form": form, "error": "Code sent"},
            )
    else:
        form = SignupForm()
    return TemplateResponse(request, "registration/signup.html", {"form": form})
