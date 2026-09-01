"""Document access control in one place.

``can_access`` is used by both the views and the presigned-URL generator so
the rule cannot drift between them:

- approved + public: everyone
- approved + registered: authenticated users
- private: owner and staff only
- pending/rejected/flagged/taken_down: owner and staff only
"""

from django.contrib.auth.models import AnonymousUser

from accounts.models import User

from .models import Document


def can_access(user: User | AnonymousUser, document: Document) -> bool:
    if getattr(user, "is_staff", False):
        return True
    is_owner = (
        user.is_authenticated
        and document.uploader_id is not None
        and document.uploader_id == user.pk
    )
    if is_owner:
        return True
    if document.moderation_status != Document.ModerationStatus.APPROVED:
        return False
    if document.visibility == Document.Visibility.PUBLIC:
        return True
    if document.visibility == Document.Visibility.REGISTERED:
        return user.is_authenticated
    return False  # private
