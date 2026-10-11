import re
from html import escape
from html.parser import HTMLParser
from urllib.parse import urlparse


ALLOWED_TAGS = {
    "a", "b", "blockquote", "body", "br", "div", "em", "h1", "h2", "h3", "h4",
    "hr", "html", "i", "li", "ol", "p", "span", "strong", "table", "tbody",
    "td", "th", "thead", "tr", "u", "ul",
}
VOID_TAGS = {"br", "hr"}
BLOCKED_TAGS = {"embed", "form", "iframe", "object", "script", "style", "svg"}
GLOBAL_ATTRIBUTES = {"class", "style"}
TAG_ATTRIBUTES = {
    "a": {"href", "rel", "target", "title"},
    "table": {"cellpadding", "cellspacing", "role"},
    "td": {"colspan", "rowspan"},
    "th": {"colspan", "rowspan", "scope"},
}
SAFE_PLACEHOLDER_URLS = {"{{reset_url}}", "{{safe_link}}", "#"}


def _safe_url(value: str) -> bool:
    stripped = value.strip()
    if stripped in SAFE_PLACEHOLDER_URLS or stripped.startswith(("/", "./", "../")):
        return True
    parsed = urlparse(stripped)
    return parsed.scheme.lower() in {"http", "https", "mailto"}


def _safe_style(value: str) -> str:
    if re.search(r"(?:expression\s*\(|url\s*\(|@import|javascript:|behavior\s*:)", value, re.I):
        return ""
    return value


class _SafeEmailHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.blocked_depth = 0

    def handle_starttag(self, tag: str, attrs):
        normalized = tag.lower()
        if normalized in BLOCKED_TAGS:
            self.blocked_depth += 1
            return
        if self.blocked_depth or normalized not in ALLOWED_TAGS:
            return

        allowed = GLOBAL_ATTRIBUTES | TAG_ATTRIBUTES.get(normalized, set())
        clean_attrs = []
        for raw_name, raw_value in attrs:
            name = raw_name.lower()
            value = raw_value or ""
            if name.startswith("on") or name not in allowed:
                continue
            if name == "href" and not _safe_url(value):
                continue
            if name == "style":
                value = _safe_style(value)
                if not value:
                    continue
            if name == "target" and value not in {"_blank", "_self"}:
                continue
            clean_attrs.append(f'{name}="{escape(value, quote=True)}"')

        suffix = f" {' '.join(clean_attrs)}" if clean_attrs else ""
        self.parts.append(f"<{normalized}{suffix}>")

    def handle_startendtag(self, tag: str, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str):
        normalized = tag.lower()
        if normalized in BLOCKED_TAGS:
            self.blocked_depth = max(0, self.blocked_depth - 1)
            return
        if self.blocked_depth or normalized not in ALLOWED_TAGS or normalized in VOID_TAGS:
            return
        self.parts.append(f"</{normalized}>")

    def handle_data(self, data: str):
        if not self.blocked_depth:
            self.parts.append(escape(data))


def sanitize_email_html(raw_html: str | None) -> str | None:
    if raw_html is None:
        return None
    parser = _SafeEmailHTMLParser()
    parser.feed(raw_html)
    parser.close()
    return "".join(parser.parts).strip()
