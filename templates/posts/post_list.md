# Apuntes de la comunidad

Apuntes escritos por usuarios de {{ SITE_NAME }}.

{% for post in posts %}- [{{ post.display_title }}]({{ SITE_URL }}{{ post.get_absolute_url }}) — {{ post.author_display }}{% if post.published_at %}, {{ post.published_at|date:"d/m/Y" }}{% endif %}
{% endfor %}
