from django.urls import reverse
from jinja2 import Environment
from markupsafe import Markup, escape


def richtext(value):
    paragraphs = []
    for block in (value or "").strip().split("\n\n"):
        lines = "<br>".join(str(escape(line.strip())) for line in block.splitlines() if line.strip())
        if lines:
            paragraphs.append("<p>" + lines + "</p>")
    return Markup("".join(paragraphs))


def safe_internal_url(value):
    value = str(value or "")
    return value if value.startswith("/") and not value.startswith("//") and "\\" not in value else "#"


def environment(**options):
    env = Environment(**options)
    env.globals["url_for"] = lambda name, **kwargs: reverse(name, kwargs=kwargs)
    env.filters["richtext"] = richtext
    env.filters["safe_internal_url"] = safe_internal_url
    return env
