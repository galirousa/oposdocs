# {{ SITE_NAME }}

Plataforma de documentos para preparar oposiciones en España: convocatorias y
bases oficiales del BOE, temarios editoriales y apuntes de opositores.

## Oposiciones destacadas

{% for op in featured %}- [{{ op.derived_title }}]({{ SITE_URL }}{{ op.get_absolute_url }}) — grupo {{ op.grupo }}, {{ op.get_ambito_display|lower }}
{% endfor %}
{% if convocatorias_abiertas %}
## Convocatorias con plazo abierto

{% for conv in convocatorias_abiertas %}- [{{ conv.oposicion.derived_title }} — {{ conv.anio }}]({{ SITE_URL }}{{ conv.get_absolute_url }}){% if conv.fecha_limite_solicitud %} (hasta {{ conv.fecha_limite_solicitud|date:"d/m/Y" }}){% endif %}
{% endfor %}{% endif %}
[Índice completo de oposiciones]({{ SITE_URL }}/oposiciones/)
