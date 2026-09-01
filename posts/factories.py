import factory
from django.utils import timezone

from accounts.factories import UserFactory

from .models import Post


class PostFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Post

    author = factory.SubFactory(UserFactory)
    title = factory.Sequence(lambda n: f"Cómo estudiar el tema {n} del temario")
    body = (
        "## Punto de partida\n\n"
        "Este apunte resume el tema con **ideas clave**, una lista de "
        "conceptos y un cuadro final.\n\n"
        "- Primer concepto que hay que memorizar sí o sí.\n"
        "- Segundo concepto, que suele caer en el examen práctico.\n\n"
        "> La clave está en repasar el esquema cada semana.\n"
    )
    status = Post.Status.PUBLISHED
    moderation_status = Post.ModerationStatus.APPROVED
    published_at = factory.LazyFunction(timezone.now)


class DraftPostFactory(PostFactory):
    title = ""
    body = ""
    status = Post.Status.DRAFT
    published_at = None
    draft_title = factory.Sequence(lambda n: f"Borrador sin terminar {n}")
    draft_body = "Todavía estoy escribiendo **esto**."
    draft_saved_at = factory.LazyFunction(timezone.now)
