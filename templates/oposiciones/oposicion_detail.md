# Oposición a {{ oposicion.derived_title }}

{{ oposicion.answer_paragraph }}

| Dato | Valor |
| --- | --- |
{% for label, value in facts %}| {{ label }} | {{ value }} |
{% endfor %}
{% if oposicion.descripcion %}{{ oposicion.descripcion }}

{% endif %}## Temario

{% for tema in oposicion.temas.all %}- Tema {{ tema.numero }}. {{ tema.titulo }}
{% empty %}(Temario pendiente de carga.)
{% endfor %}
## Convocatorias

{% for conv in oposicion.convocatorias.all %}- [Convocatoria {{ conv.anio }}]({{ SITE_URL }}{{ conv.get_absolute_url }}): {{ conv.get_estado_display|lower }}{% if conv.plazas %}, {{ conv.plazas }} plazas{% endif %}
{% empty %}(Sin convocatorias registradas.)
{% endfor %}
## Documentos

{% for doc in documents %}- [{{ doc.title }}]({{ SITE_URL }}{{ doc.get_absolute_url }})
{% empty %}(Sin documentos publicados.)
{% endfor %}
