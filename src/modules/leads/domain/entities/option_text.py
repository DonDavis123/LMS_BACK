from enum import Enum


def option_text(value):
    """The plain text of a dropdown value.

    Lead Source / Status / Industry / Rating used to be fixed enums and are
    now free text chosen from each company's own options. Old code (and old
    tests) may still hand in an enum member; this turns it into its text and
    leaves ordinary strings (and None) untouched.
    """
    return value.value if isinstance(value, Enum) else value
