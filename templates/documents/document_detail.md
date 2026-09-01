# {{ document.title }}

{% if document.description %}{{ document.description }}

{% endif %}| Dato | Valor |
| --- | --- |
{% for label, value in facts %}| {{ label }} | {{ value }} |
{% endfor %}
{% if document.text_preview %}## Vista previa del contenido

{{ document.text_preview }}
{% endif %}
