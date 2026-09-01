# Convocatorias de {{ oposicion.derived_title }}

{% for conv in convocatorias %}- [{{ conv.anio }}]({{ SITE_URL }}{{ conv.get_absolute_url }}): {{ conv.get_estado_display|lower }}{% if conv.plazas %}, {{ conv.plazas }} plazas{% endif %}{% if conv.referencia_boe %} ({{ conv.referencia_boe }}){% endif %}
{% empty %}(Sin convocatorias registradas.)
{% endfor %}
