# Account Email Troubleshooting

CytoCV password recovery only works for email addresses that already belong to a
CytoCV user account. Password recovery must not create accounts.

## Check an account

```bash
python manage.py shell -c "
from django.contrib.auth import get_user_model
from allauth.account.models import EmailAddress
emails = [
    'active-user@example.edu',
    'missing-user@example.edu',
    'scientist@biochem.example.edu',
]
User = get_user_model()
for e in emails:
    print('\\nEMAIL', e)
    print('users:', list(User.objects.filter(email__iexact=e).values('id','email','is_active')))
    print('aliases:', list(EmailAddress.objects.filter(email__iexact=e).values('id','user_id','email','verified','primary')))
"
```

## Repair a user that already exists

Use this when `User.email` exists but the matching allauth `EmailAddress` row is
missing or stale.

```bash
python manage.py sync_user_email_addresses --email active-user@example.edu --dry-run
python manage.py sync_user_email_addresses --email active-user@example.edu
```

The command is idempotent. It creates or updates a verified primary alias for the
existing user and reports conflicts instead of reassigning another user's alias.

## Create an operator-managed account

Use this when the email has no existing `User` row. The command creates an active
user with an unusable password and a verified primary email alias. The user can
then use password recovery to set a password.

```bash
python manage.py create_or_invite_user --email scientist@biochem.example.edu
```

Do not expect password recovery to create missing accounts. If both
`User` and `EmailAddress` are absent, an admin/operator must create the account
first.
