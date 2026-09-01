# Temario de {{ oposicion.derived_title }}

{{ total_temas }} temas.

{% for bloque, temas in bloques.items %}{% if bloque %}## {{ bloque }}

{% endif %}{% for tema in temas %}{{ tema.numero }}. {{ tema.titulo }}
{% endfor %}
{% endfor %}
