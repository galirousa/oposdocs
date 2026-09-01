"""Markdown rendering and sanitising: the part that user input reaches first."""

from posts.rendering import render_markdown, strip_html


class TestRenderMarkdown:
    def test_renders_basic_formatting(self):
        html = render_markdown("Esto es **importante** y esto *no*.")
        assert "<strong>importante</strong>" in html
        assert "<em>no</em>" in html

    def test_renders_lists_quotes_and_tables(self):
        html = render_markdown("- uno\n- dos\n\n> una cita\n\n| a | b |\n| - | - |\n| 1 | 2 |")
        assert "<ul>" in html and "<li>uno</li>" in html
        assert "<blockquote>" in html
        assert "<table>" in html and "<th>a</th>" in html

    def test_headings_are_demoted_so_the_page_keeps_one_h1(self):
        html = render_markdown("# Título del autor\n\n## Subapartado")
        assert "<h1>" not in html
        assert "<h2>Título del autor</h2>" in html
        assert "<h3>Subapartado</h3>" in html

    def test_script_tags_are_stripped(self):
        html = render_markdown("Hola <script>alert('xss')</script> mundo")
        assert "<script" not in html
        assert "alert" not in html

    def test_event_handlers_and_styles_are_stripped(self):
        html = render_markdown('<p onclick="steal()" style="color:red">texto</p>')
        assert "onclick" not in html
        assert "style" not in html
        assert "texto" in html

    def test_javascript_urls_are_stripped(self):
        html = render_markdown("[pincha](javascript:alert(1))")
        assert "javascript:" not in html

    def test_external_links_are_nofollow_ugc(self):
        html = render_markdown("[enlace](https://ejemplo.es)")
        assert 'href="https://ejemplo.es"' in html
        assert "nofollow" in html and "ugc" in html

    def test_iframes_are_stripped(self):
        html = render_markdown('<iframe src="https://ejemplo.es"></iframe>')
        assert "<iframe" not in html

    def test_empty_input(self):
        assert render_markdown("") == ""
        assert render_markdown("   \n  ") == ""


class TestStripHtml:
    def test_returns_plain_text(self):
        text = strip_html("<h2>Uno</h2><p>Dos <strong>tres</strong></p>")
        assert text == "Uno Dos tres"

    def test_unescapes_entities(self):
        assert strip_html("<p>Ley 34/2002 &amp; LSSI</p>") == "Ley 34/2002 & LSSI"
