"""Create/refresh the role groups from the section 7 permission matrix.

Idempotent: run it after every deploy (it is part of the migrate step in the
Makefile). Roles:

- Registered: download, upload (post-verification), write posts, vote, report.
- Contributor: as Registered, but uploads skip the moderation queue.
- Moderator: approve/reject documents, handle reports.
- Editor: manage oposiciones, convocatorias, temas and official documents.
- Admin: staff flag + superuser managed separately in the user admin.
"""

from typing import Any

from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand

ROLE_PERMISSIONS: dict[str, list[str]] = {
    "Registered": [
        "documents.add_document",
        "documents.add_report",
        "posts.add_post",
        "posts.change_post",
        "posts.delete_post",
    ],
    "Contributor": [
        "documents.add_document",
        "documents.add_report",
        "posts.add_post",
        "posts.change_post",
        "posts.delete_post",
    ],
    "Moderator": [
        "documents.view_document",
        "documents.change_document",
        "documents.view_report",
        "documents.change_report",
        "documents.view_moderationlog",
        "posts.view_post",
        "posts.change_post",
    ],
    "Editor": [
        "oposiciones.add_oposicion",
        "oposiciones.change_oposicion",
        "oposiciones.view_oposicion",
        "oposiciones.add_convocatoria",
        "oposiciones.change_convocatoria",
        "oposiciones.view_convocatoria",
        "oposiciones.add_tema",
        "oposiciones.change_tema",
        "oposiciones.delete_tema",
        "oposiciones.view_tema",
        "documents.add_document",
        "documents.change_document",
        "documents.view_document",
    ],
    "Admin": [],  # granted via is_superuser, kept as a group for labelling
}


class Command(BaseCommand):
    help = "Create or update the role groups and their permissions."

    def handle(self, *args: Any, **options: Any) -> None:
        for role, perm_labels in ROLE_PERMISSIONS.items():
            group, _ = Group.objects.get_or_create(name=role)
            perms = []
            for label in perm_labels:
                app_label, codename = label.split(".")
                try:
                    perms.append(
                        Permission.objects.get(content_type__app_label=app_label, codename=codename)
                    )
                except Permission.DoesNotExist:
                    self.stderr.write(f"Missing permission {label}; run migrate first.")
            group.permissions.set(perms)
            self.stdout.write(f"Synced role {role} ({len(perms)} permissions)")
