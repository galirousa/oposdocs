from django.db import models


class ConsentEvent(models.Model):
    """Server-side audit log of consent decisions (client stores the state)."""

    class Decision(models.TextChoices):
        ACCEPTED = "accepted", "Aceptado"
        REJECTED = "rejected", "Rechazado"

    decision = models.CharField("decisión", max_length=10, choices=Decision.choices)
    # Anonymous by design: no IP, no user FK; enough for an audit trail of volumes.
    user_agent_hash = models.CharField("hash de user agent", max_length=64, blank=True)
    created_at = models.DateTimeField("fecha", auto_now_add=True)

    class Meta:
        verbose_name = "evento de consentimiento"
        verbose_name_plural = "eventos de consentimiento"

    def __str__(self) -> str:
        return f"{self.decision} @ {self.created_at:%Y-%m-%d %H:%M}"
