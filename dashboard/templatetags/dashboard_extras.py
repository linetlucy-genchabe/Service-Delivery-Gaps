from django import template

register = template.Library()


@register.filter
def dict_get(d, key):
    """Look up `key` in dict `d` — for when the key is a template variable
    (e.g. a loop variable) rather than a literal, which Django's built-in
    dot lookup can't do."""
    if d is None:
        return None
    return d.get(key)
