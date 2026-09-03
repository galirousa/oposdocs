"""The non-interactive admin bootstrap, including its production guard."""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.management.base import CommandError

pytestmark = pytest.mark.django_db

User = get_user_model()


class TestCreateAdmin:
    def test_creates_a_superuser_with_the_placeholder_password(self, settings):
        settings.DEBUG = True
        call_command("create_admin")
        user = User.objects.get(username="admin")
        assert user.is_superuser and user.is_staff
        assert user.check_password("opos-admin-2026")

    def test_is_idempotent(self, settings):
        settings.DEBUG = True
        call_command("create_admin")
        call_command("create_admin")
        assert User.objects.filter(username="admin").count() == 1

    def test_accepts_an_explicit_password(self, settings):
        settings.DEBUG = False
        call_command("create_admin", "--password", "un-secreto-de-verdad")
        assert User.objects.get(username="admin").check_password("un-secreto-de-verdad")

    def test_refuses_the_placeholder_when_debug_is_off(self, settings):
        settings.DEBUG = False
        with pytest.raises(CommandError, match="placeholder"):
            call_command("create_admin")
        assert not User.objects.filter(username="admin").exists()

    def test_placeholder_can_be_forced(self, settings):
        settings.DEBUG = False
        call_command("create_admin", "--force-default-password")
        assert User.objects.get(username="admin").check_password("opos-admin-2026")

    def test_keep_password_leaves_an_existing_one_alone(self, settings):
        settings.DEBUG = True
        call_command("create_admin", "--password", "primera")
        call_command("create_admin", "--keep-password")
        assert User.objects.get(username="admin").check_password("primera")

    def test_joins_the_admin_group_when_roles_are_synced(self, settings):
        settings.DEBUG = True
        Group.objects.create(name="Admin")
        call_command("create_admin")
        assert User.objects.get(username="admin").groups.filter(name="Admin").exists()

    def test_password_from_settings_is_used(self, settings):
        """DJANGO_ADMIN_PASSWORD in the environment must actually take effect."""
        settings.DEBUG = False
        settings.DJANGO_ADMIN_PASSWORD = "clave-del-servidor"
        call_command("create_admin")
        assert User.objects.get(username="admin").check_password("clave-del-servidor")

    def test_username_and_email_come_from_settings(self, settings):
        settings.DEBUG = False
        settings.DJANGO_ADMIN_USERNAME = "jefa"
        settings.DJANGO_ADMIN_EMAIL = "jefa@oposdocs.example"
        settings.DJANGO_ADMIN_PASSWORD = "clave-del-servidor"
        call_command("create_admin")
        user = User.objects.get(username="jefa")
        assert user.email == "jefa@oposdocs.example"

    def test_the_created_admin_can_actually_log_in_to_the_admin_site(self, client, settings):
        """The whole point: these credentials must open /admin/ on the server."""
        settings.DEBUG = False
        settings.DJANGO_ADMIN_PASSWORD = "clave-del-servidor"
        call_command("create_admin")

        assert client.login(username="admin", password="clave-del-servidor")
        response = client.get("/admin/")
        assert response.status_code == 200

    def test_login_survives_a_second_bootstrap_run(self, client, settings):
        """Re-running create_admin on every deploy must not lock the admin out."""
        settings.DEBUG = False
        settings.DJANGO_ADMIN_PASSWORD = "clave-del-servidor"
        call_command("create_admin")
        call_command("create_admin")
        assert client.login(username="admin", password="clave-del-servidor")

    def test_promotes_an_existing_plain_user(self, settings):
        settings.DEBUG = True
        User.objects.create_user(username="admin", email="admin@example.com", password="x")
        call_command("create_admin")
        user = User.objects.get(username="admin")
        assert user.is_superuser and user.is_staff
