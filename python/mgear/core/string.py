"""String management methods"""

# Stdlib imports
import re


def normalize(string):
    """Replaces invalid characters with an underscore character

    string.normalize will add an "_" character in front of the returned string
    if the input starts with an intiger

    Args:
        string(str): A string to normalize
    Returns:
        str: Normalized string

    Note:
        Invalid characters are punctuiation and most of the symbols.
    """

    string = str(string)
    if re.match("^[0-9]", string):
        string = "_" + string

    return re.sub("[^A-Za-z0-9_-]", "_", str(string))


# def removeInvalidCharacter(string):
#     """Removes all invalid characters

#     Args:
#         string(str): A string to normalize
#     Returns:
#         str: Normalized string

#     Note:
#         Invalid characters are punctuiation and most of the symbols.
#     """

#     return re.sub("[^A-Za-z0-9]", "", str(string))
