from django import template

register = template.Library()

@register.filter(name="filesize")
def filesize(value):
    """
    Convert bytes to kilobytes, megabytes, gigabytes, etc...
    :param value:integer in bytes
    :return: string in kilobytes, megabytes, gigabytes, etc...
    """
    units = ['bytes','KB','MB','GB','TB']

    if value == 0:
        return '0 bytes'
    i = 0
    while value >= 1024 and i < len(units) - 1:
        value /= 1024.0
        i += 1
    return f"{value:.2f} {units[i]}"