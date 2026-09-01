# {{ post.display_title }}

Por {{ post.author_display }}{% if post.published_at %} · {{ post.published_at|date:"d/m/Y" }}{% endif %} · {{ post.reading_time }} min

{{ post.body }}

| Dato | Valor |
| --- | --- |
{% for label, value in facts %}| {{ label }} | {{ value }} |
{% endfor %}
