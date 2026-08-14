from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

from references.models import CITATION_STYLES
from references.services.citations import split_emphasis

register = template.Library()


@register.filter
def author_short(authors):
    if not authors:
        return "Autoria não informada"
    first = authors[0]
    name = first.get("family") or first.get("literal") or "Autoria não informada"
    return f"{name} et al." if len(authors) > 1 else name


@register.filter
def style_label(value):
    return dict(CITATION_STYLES).get(value, value)


@register.filter
def source_label(value):
    labels = {
        "manual": "Manual",
        "pdf": "PDF",
        "docx": "DOCX",
        "pptx": "PPTX",
        "url": "URL",
    }
    return labels.get(value, value.upper())


@register.filter
def citation_html(item):
    markup = "".join(
        f"<em>{escape(value)}</em>" if emphasized else escape(value)
        for value, emphasized in split_emphasis(item.text, item.reference)
    )
    return mark_safe(markup)
