"""String management methods"""

# Stdlib imports
import re


def convert_RL_name(name):
    """Switch R-L or L-R presceding, following or in-between underscores

    Args:
        name(str): String to operate on
    Returns:
        str: Switched name

    Example:
        _L -> _R /  _L0_ -> _R0_ / L_ > R_ ...
    """

    # If the input is just L or R return the converted
    if name == "L":
        return "R"
    elif name == "R":
        return "L"

    # Creates pattern
    re_str = "_[RL][0-9]+_|^[RL][0-9]+_|_[RL][0-9]+$|_[RL]_|^[RL]_|_[RL]$"
    re_pattern = re.compile(re_str)

    # Search for matches
    re_match = re.search(re_pattern, name)

    # Returns unchanged name if nothing matches
    if not re_match:
        return name

    instance = re_match.group(0)
    if instance.find("R") != -1:
        rep = instance.replace("R", "L")
    else:
        rep = instance.replace("L", "R")

    name = re.sub(re_pattern, rep, name)
    return name


def normalize(string, force_underscore=False):
    """Replaces invalid characters with an underscore character

    string.normalize will add an "_" character in front of the returned string
    if the input starts with an intiger

    Args:
        string(str): A string to normalize
        force_underscore(bool): Convert hyphens to underscores
    Returns:
        str: Normalized string

    Note:
        Invalid characters are punctuation and most of the symbols.
    """

    string = str(string)
    if re.match("^[0-9]", string):
        string = "_" + string

    if force_underscore:
        token = "[^A-Za-z0-9_]"
    else:
        token = "[^A-Za-z0-9_-]"

    return re.sub(token, "_", str(string))


def remove_invalid_characters(string):
    """Removes all invalid characters

    Args:
        string(str): A string to normalize
    Returns:
        str: Normalized string

    Note:
        Invalid characters are punctuation and all symbols.
    """

    return re.sub("[^A-Za-z0-9]", "", str(string))


def replace_sharps_with_padding(string, index):
    """Replaces # symbols on a string with properly padded indexing

    Args:
        string(str): String to operate on. Sould contain '#' characters
        index(int): Index value
    Returns:
        str: sIndexed string

    Example:
        count_### > count_001
    """

    # Adds end sharp character if none found
    if string.count("#") == 0:
        string += "#"

    digit = str(index)
    while len(digit) < string.count("#"):
        digit = "0" + digit

    return re.sub("#+", digit, string)
