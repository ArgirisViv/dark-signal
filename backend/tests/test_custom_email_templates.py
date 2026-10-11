from app.models.email_template import EmailTemplate
from app.services.email_templates import create_custom_template


class DummySession:
    def __init__(self, existing_keys=None):
        self.existing_keys = set(existing_keys or [])
        self.added = []
        self.committed = False

    def query(self, model):
        return self

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return None

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.committed = True

    def refresh(self, obj):
        return None


def test_create_custom_template_uses_sanitized_key_and_name():
    session = DummySession()

    template = create_custom_template(
        session,
        key="My Custom Template",
        name="My Custom Template",
        subject="Custom subject",
        body_text="Hello there",
        body_html="<p>Hello there</p>",
    )

    assert isinstance(template, EmailTemplate)
    assert template.key == "my_custom_template"
    assert template.name == "My Custom Template"
    assert template.subject == "Custom subject"
    assert template.body_text == "Hello there"
    assert template.body_html == "<p>Hello there</p>"
    assert session.committed is True


def test_create_custom_template_sanitizes_unsafe_html():
    session = DummySession()

    template = create_custom_template(
        session,
        key="unsafe",
        name="Unsafe template",
        subject="Test",
        body_html=(
            '<p onclick="alert(1)">Hello</p>'
            '<a href="javascript:alert(1)">Open</a>'
            '<script>alert("unsafe")</script>'
        ),
    )

    assert "onclick" not in template.body_html
    assert "javascript:" not in template.body_html
    assert "<script" not in template.body_html
    assert "unsafe" not in template.body_html
    assert "<p>Hello</p>" in template.body_html
