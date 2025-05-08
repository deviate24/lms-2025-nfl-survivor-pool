from django import template
from django.template.defaultfilters import stringfilter

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """
    Gets an item from a dictionary safely.
    Returns None if the key doesn't exist or if the dictionary is None.
    
    Usage: {{ dictionary|get_item:key }}
    """
    if dictionary is None:
        return None
    
    if key is None:
        return None
        
    return dictionary.get(key)

@register.filter
def getattr(obj, attr):
    """
    Gets an attribute from an object safely.
    Returns None if the attribute doesn't exist or if the object is None.
    
    Usage: {{ object|getattr:"attribute_name" }}
    """
    if obj is None:
        return None
    
    if attr is None:
        return None
    
    try:
        return getattr(obj, attr)
    except (AttributeError, TypeError):
        try:
            return obj[attr]
        except (KeyError, TypeError):
            return None

@register.filter
def addstr(arg1, arg2):
    """
    Concatenates two strings.
    
    Usage: {{ string1|addstr:string2 }}
    """
    return str(arg1) + str(arg2)

@register.filter
def getitem(dictionary, key):
    """
    Gets an item from a dictionary, similar to get_item.
    This is a duplicate to ensure compatibility with both naming conventions.
    
    Usage: {{ dictionary|getitem:key }}
    """
    if dictionary is None:
        return None
    
    if key is None:
        return None
        
    return dictionary.get(key)
