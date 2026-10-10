"""Admin provisioning tool.

Creates or promotes a user to the admin area. There is deliberately NO public
or self-service registration endpoint that grants administrator access; admins
are only ever provisioned from the command line (or Django's superuser flow).
"""

import getpass

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.common.permissions import is_admin_account

User = get_user_model()


class Command(BaseCommand):
    help = 'Create an administrator account or promote an existing user.'

    def add_arguments(self, parser):
        parser.add_argument('email', nargs='?', help='Account email address.')
        parser.add_argument('--password', help='Account password (prompted if omitted).')
        parser.add_argument(
            '--role',
            default='admin',
            help='Role to assign (default: admin). Only trusted values are allowed.',
        )

    def handle(self, *args, **options):
        email = (options.get('email') or '').strip().lower()
        if not email:
            raise CommandError('An email address is required.')

        role = options.get('role') or 'admin'
        if role not in {'admin', 'superadmin'}:
            raise CommandError(f'Refusing to assign untrusted role: {role}')

        password = options.get('password') or getpass.getpass('Password: ')
        if len(password or '') < 8:
            raise CommandError('Password must be at least 8 characters long.')

        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            user = User.objects.create_user(email=email, password=password)
            self.stdout.write(self.style.SUCCESS(f'Created new account {email}'))
        else:
            user.set_password(password)
            user.is_active = True

        user.role = role
        user.is_staff = True
        user.is_superuser = role == 'superadmin'
        user.is_verified = True
        user.save()

        if not is_admin_account(user):
            raise CommandError(f'Account {email} failed the admin authorization check.')

        self.stdout.write(self.style.SUCCESS(
            f'Admin {email} provisioned (role={role}, is_staff=True, is_superuser={user.is_superuser}).'
        ))