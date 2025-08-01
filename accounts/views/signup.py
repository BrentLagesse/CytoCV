from django.template.response import TemplateResponse
from django.shortcuts import redirect
from django.core.mail import send_mail
from django.conf import settings
from .forms import SignupForm

import uuid

def signup(request):
    # Initialize verify_code from session if it exists
    verify_code = request.session.get('verify_code', None)
    if request.method == 'POST':
        form = SignupForm(request.POST)
        if form.is_valid():
            # save the user if success and redirect to login page
            if 'submit' in request.POST:
                print(verify_code)
                code = form.cleaned_data['verify_code']
                if not code:
                    return TemplateResponse(request,"registration/signup.html", {'form':form,'error':'Please enter a verification code'})
                else:
                    if not verify_code:
                        return TemplateResponse(request,"registration/signup.html", {'form':form,'error':'Please send a verification code'})
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
            return TemplateResponse(request,"registration/signup.html", {'form':form,'error':'Code sent'})
    else:
        form = SignupForm()
    return TemplateResponse(request, "registration/signup.html", {'form':form})