"""Create (or reset) a superuser without the interactive prompt.

Exists so a fresh environment can be brought up in one command. The default
password is a development placeholder: the command refuses to use it when
DEBUG is off, so a production superuser has to be given a real one via
DJANGO_ADMIN_PASSWORD or --password.
"""

from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError

DEFAULT_USERNAME = "admin"
DEFAULT_EMAIL = "admin@example.com"
DEFAULT_PASSWORD = "opos-admin-2026"


class Command(BaseCommand):
    help = "Create or update the admin superuser non-interactively."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--username", default=None)
        parser.add_argument("--email", default=None)
        parser.add_argument("--password", default=None)
        parser.add_argument(
            "--force-default-password",
            action="store_true",
            help="Allow the placeholder password even when DEBUG is off.",
        )
        parser.add_argument(
            "--keep-password",
            action="store_true",
            help="Do not touch the password if the user already exists.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        user_model = get_user_model()
        username = options["username"] or getattr(
            settings, "DJANGO_ADMIN_USERNAME", DEFAULT_USERNAME
        )
        email = options["email"] or getattr(settings, "DJANGO_ADMIN_EMAIL", DEFAULT_EMAIL)
        password = options["password"] or getattr(settings, "DJANGO_ADMIN_PASSWORD", "")

        using_default = not password
        if using_default:
            password = DEFAULT_PASSWORD
            if not settings.DEBUG and not options["force_default_password"]:
                raise CommandError(
                    "Refusing to set the placeholder password with DEBUG off. "
                    "Set DJANGO_ADMIN_PASSWORD, pass --password, or accept the "
                    "risk with --force-default-password."
                )

        username_field = user_model.USERNAME_FIELD
        lookup = {username_field: username if username_field != "email" else email}
        user, created = user_model.objects.get_or_create(
            **lookup, defaults={"is_staff": True, "is_superuser": True}
        )
        if hasattr(user, "email") and not user.email:
            user.email = email
        user.is_staff = True
        user.is_superuser = True
        if created or not options["keep_password"]:
            user.set_password(password)
        user.save()

        admin_group = Group.objects.filter(name="Admin").first()
        if admin_group:
            user.groups.add(admin_group)

        verb = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(f"{verb} superuser {username!r} <{email}>"))
        if created or not options["keep_password"]:
            shown = password if using_default else "(from DJANGO_ADMIN_PASSWORD/--password)"
            self.stdout.write(f"Password: {shown}")
            self.stdout.write(
                self.style.WARNING("Change it after first login: /admin/password_change/")
            )
