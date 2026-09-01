import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Site user.

    ``external_id`` is a stable identifier separate from the email address so a
    future migration to an external identity provider cannot orphan uploads.
    """

    external_id = models.UUIDField(
        default=uuid.uuid4, unique=True, editable=False, verbose_name="ID externo"
    )
    email = models.EmailField("dirección de correo", unique=True)

    class Meta:
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"

    def __str__(self) -> str:
        return self.email or self.username
