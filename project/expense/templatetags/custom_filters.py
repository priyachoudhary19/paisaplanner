from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """Get item from dictionary by key."""
    if isinstance(dictionary, list):
        # For list of tuples like month_options
        for k, v in dictionary:
            if k == key:
                return v
        return ""
    return dictionary.get(key, "")