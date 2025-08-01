from django.template.response import TemplateResponse
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect

def auth_login(request):
    if request.method == "POST":
        # getting username and password
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None: # login success
            login(request, user)
            return redirect('profile')
        else: # not matching credential
            return TemplateResponse(request, 'registration/login.html', {'error': 'Invalid credentials'})
    return TemplateResponse(request, "registration/login.html", {})

def auth_logout(request):
    logout(request)
    return redirect('homepage')