from django.template.response import TemplateResponse
from django.contrib.auth import authenticate, login
from django.contrib.auth.forms import AuthenticationForm
# test user:
# username: timmy
# password: 12345
from django.views.decorators.csrf import csrf_exempt

def auth_login(request):
    form = AuthenticationForm(data=request.POST)

    if request.method == "POST":
        username = request.POST.get('username')
        password = request.POST.get('password')
        print(username, password)
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            print("Login Successful")
        else:
            print("Login failed")
            return TemplateResponse(request, 'registration/login.html', {'error': 'Invalid credentials'})
    return TemplateResponse(request, "registration/login.html", {})