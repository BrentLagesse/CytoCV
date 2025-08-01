from django.apps import AppConfig

# this is use to create guest user on start up
class AccountsConfig(AppConfig):
    name = 'accounts'

    def ready(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            User.objects.get_or_create(username='guest',defaults={'is_active':False}) # create a guest user
            # this is inactive and placeholder for not log in user
        except:
            pass