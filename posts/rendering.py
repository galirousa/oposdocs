"""Markdown → sanitised HTML for user-written posts.

Two rules drive this module:

- **Render on save, never on read.** Constraint 1 in CLAUDE.md requires the
  finished content in the initial HTML response, so a post stores its rendered
  HTML (``Post.body_html``) and the read path is a single query with no
  markdown pass and no client-side rendering.
- **Render then sanitise, with an allowlist.** Markdown deliberately passes raw
  HTML through, and this is user-generated content, so everything the allowlist
  does not name is dropped after rendering.
"""

import html as html_module

import markdown as markdown_lib
import nh3
from markdown.extensions import Extension
from markdown.treeprocessors import Treeprocessor

ALLOWED_TAGS = {
    "p", "br", "hr", "div", "span",
    "h2", "h3", "h4", "h5", "h6",
    "strong", "b", "em", "i", "u", "s", "del", "ins", "sup", "sub", "mark", "small",
    "ul", "ol", "li", "dl", "dt", "dd",
    "blockquote", "pre", "code", "kbd", "samp",
    "a", "img", "figure", "figcaption",
    "table", "thead", "tbody", "tfoot", "tr", "th", "td", "caption",
}  # fmt: skip

ALLOWED_ATTRIBUTES = {
    "a": {"href", "title"},
    "img": {"src", "alt", "title", "width", "height", "loading"},
    "ol": {"start"},
    "td": {"align", "colspan", "rowspan"},
    "th": {"align", "colspan", "rowspan", "scope"},
    "code": {"class"},
    "pre": {"class"},
}

ALLOWED_SCHEMES = {"http", "https", "mailto"}

# Outbound links in user content carry nofollow+ugc: an open editor is a
# spam-link magnet and this site's organic ranking is the business model.
LINK_REL = "nofollow ugc noopener noreferrer"

# "extra" is deliberately not used: footnotes and attr_list give post authors
# more surface than the allowlist below is willing to keep.
MARKDOWN_EXTENSIONS = ["tables", "fenced_code", "sane_lists", "nl2br"]


class _HeadingShiftTreeprocessor(Treeprocessor):
    """Demote h1-h5 by one level.

    The page's own <h1> is the post title. A second <h1> inside the body
    muddies the document outline crawlers build from the page.
    """

    def run(self, root: object) -> None:
        for element in root.iter():  # type: ignore[attr-defined]
            if element.tag in {"h1", "h2", "h3", "h4", "h5"}:
                element.tag = f"h{int(element.tag[1]) + 1}"


class _HeadingShiftExtension(Extension):
    def extendMarkdown(self, md: markdown_lib.Markdown) -> None:  # noqa: N802 (markdown API)
        md.treeprocessors.register(_HeadingShiftTreeprocessor(md), "heading_shift", 5)


def render_markdown(text: str) -> str:
    """Markdown source → HTML that is safe to insert into a page."""
    if not text.strip():
        return ""
    # A fresh Markdown instance per call: the library's instances hold parse
    # state and are not thread-safe, and this runs once per save, not per read.
    renderer = markdown_lib.Markdown(
        extensions=[*MARKDOWN_EXTENSIONS, _HeadingShiftExtension()],
        output_format="html",
    )
    return nh3.clean(
        renderer.convert(text),
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        url_schemes=ALLOWED_SCHEMES,
        link_rel=LINK_REL,
        strip_comments=True,
    )


def strip_html(rendered_html: str) -> str:
    """Rendered HTML → plain text, for excerpts, meta descriptions and JSON-LD."""
    if not rendered_html:
        return ""
    # "</h2><p>" must not weld the heading to the paragraph that follows it.
    spaced = rendered_html.replace("><", "> <")
    text = nh3.clean(spaced, tags=set(), attributes={})
    return " ".join(html_module.unescape(text).split())
