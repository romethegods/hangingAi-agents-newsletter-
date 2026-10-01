"""Email templates (Jinja2). HTML is autoescaped; plain-text versions are not."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

_env = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "email_templates"),
    # Match on ".html.j2": escaping keys off the file name, and scraped titles go into these.
    autoescape=select_autoescape(enabled_extensions=("html.j2",), default_for_string=False),
    undefined=StrictUndefined,  # a typo in a template fails loudly instead of rendering blank
    trim_blocks=True,
    lstrip_blocks=True,
)


def render(name: str, context: dict) -> str:
    return _env.get_template(f"{name}.j2").render(**context)
