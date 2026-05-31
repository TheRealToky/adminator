"""
Create (or update) the admin user from env vars, without any demo data.

Reads DJANGO_SUPERUSER_EMAIL / DJANGO_SUPERUSER_PASSWORD / DJANGO_SUPERUSER_FULL_NAME.
Safe to run on every startup — idempotent.

Usage:
    python manage.py bootstrap_admin
    python manage.py bootstrap_admin --reset-password   # force-reset existing user's password
"""
from __future__ import annotations

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import Role


User = get_user_model()


class Command(BaseCommand):
    help = "Create or update the admin user from DJANGO_SUPERUSER_* env vars."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset-password", action="store_true",
            help="Reset the password even if the user already exists.",
        )

    def handle(self, *args, **options):
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL")
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")
        full_name = os.environ.get("DJANGO_SUPERUSER_FULL_NAME", "Site Admin")

        if not email or not password:
            raise CommandError(
                "DJANGO_SUPERUSER_EMAIL and DJANGO_SUPERUSER_PASSWORD must be set."
            )

        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "full_name": full_name,
                "role": Role.ADMIN,
                "is_staff": True,
                "is_superuser": True,
                "is_active": True,
            },
        )

        if created:
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(f"✓ Created admin: {email}"))
        elif options["reset_password"]:
            user.set_password(password)
            user.is_staff = True
            user.is_superuser = True
            user.is_active = True
            user.role = Role.ADMIN
            user.save()
            self.stdout.write(self.style.WARNING(f"✓ Reset password for: {email}"))
        else:
            self.stdout.write(self.style.NOTICE(f"Admin already exists: {email} (no change)"))
