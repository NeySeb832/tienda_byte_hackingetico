"""Template filters for money: ``{{ price|cop }}``."""

from django import template

from apps.core.money import MoneyInput, format_cop

register = template.Library()


@register.filter(name="cop")
def cop(value: MoneyInput) -> str:
    """Render an amount as COP; invalid values render as an empty string (fail safe)."""
    try:
        return format_cop(value)
    except (TypeError, ValueError):
        return ""
