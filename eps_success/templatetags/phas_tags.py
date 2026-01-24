# Django imports
from django import template

register = template.Library()


@register.filter
def index(sequence, position):
    """Return the x'th element of an iterable."""
    try:
        return sequence[int(position)]
    except (IndexError, ValueError, TypeError):
        pass
    try:
        return sequence.get(position)
    except (ValueError, TypeError):
        return None


@register.filter
def enumerate_list(value):
    """Provide numerate as a template filter"""
    try:
        return list(enumerate(value))
    except TypeError:
        return []


@register.filter
def reshape(value, cols):
    """Take an iterable and return it in chunks of cols."""
    ret = []
    values = list(value)
    endpoint = len(values)
    for i in range(0, endpoint, cols):
        ret.append(values[i : i + cols])
    return ret
