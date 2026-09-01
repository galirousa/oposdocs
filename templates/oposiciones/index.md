# Índice de oposiciones

{% for op in oposiciones %}- [{{ op.derived_title }}]({{ SITE_URL }}{{ op.get_absolute_url }}) — grupo {{ op.grupo }}, {{ op.get_ambito_display|lower }}
{% endfor %}
