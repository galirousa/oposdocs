# Convocatoria {{ convocatoria.anio }} — {{ oposicion.derived_title }}

{{ convocatoria.descripcion_jobposting }}

| Dato | Valor |
| --- | --- |
{% for label, value in facts %}| {{ label }} | {{ value }} |
{% endfor %}
{% if convocatoria.url_boe %}Texto oficial: {{ convocatoria.url_boe }}
{% endif %}
[Ficha de la oposición]({{ SITE_URL }}{{ oposicion.get_absolute_url }})
