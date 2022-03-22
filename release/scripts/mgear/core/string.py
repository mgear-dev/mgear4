"""string management methods"""

##########################################################
# GLOBAL
##########################################################
import re

##########################################################
# FUNCTIONS
##########################################################


def normalize(string):
    """Replace all invalid characters with "_"

    :param string string: A string to normalize.
    :return string: Normalized string

    """
    string = str(string)

    if re.match("^[0-9]", string):
        string = "_" + string

    return re.sub("[^A-Za-z0-9_-]", "_", str(string))


def normalize2(string):
    """Replace all invalid characters with "_". including "-"
    This ensure that the name is compatible with Maya naming rules

    :param string string: A string to normalize.
    :return string: Normalized string

    """
    string = str(string)

    if re.match("^[0-9]", string):
        string = "_" + string

    return re.sub("[^A-Za-z0-9_]", "_", str(string))


def normalize_with_padding(string):
    """Replace all invalid characters with "_". including "-"
    This ensure that the name is compatible with Maya naming rules

    Also list of # symbol with properly padded index.

    ie. count_### > count_001

    :param string string: A string to normalize.
    :return string: Normalized string

    """
    string = str(string)

    if re.match("^[0-9]", string):
        string = "_" + string

    return re.sub("[^A-Za-z0-9_#]", "_", str(string))


def removeInvalidCharacter(string):
    """Remove all invalid character.

    :param string string: A string to normalize.
    :return string: Normalized string.

    """
    return re.sub("[^A-Za-z0-9]", "", str(string))


def replaceSharpWithPadding(string, index):
    """Replace a list of # symbol with properly padded index.

    ie. count_### > count_001

    :param string string: A string to set. Should include '#'
    :param integer index: Index to replace.
    :return string: Normalized string.

    """
    if string.count("#") == 0:
        string += "#"

    digit = str(index)
    while len(digit) < string.count("#"):
        digit = "0" + digit

    return re.sub("#+", digit, string)


def convertRLName(name):
    """Convert a string with underscore

    i.e: "_\L", "_L0\_", "L\_", "_L" to "R". And vice and versa.

    :param string name: string to convert
    :return: Tuple of Integer

    """
    if name == "L":
        return "R"
    elif name == "R":
        return "L"
    elif name == "l":
        return "r"
    elif name == "r":
        return "l"

    # re_str = "_[RL][0-9]+_|^[RL][0-9]+_|_[RL][0-9]+$|_[RL]_|^[RL]_|_[RL]$"

    # adding support to conver l and r lowecase side label.
    re_str = "_[RLrl][0-9]+_|^[RLrl][0-9]+_"
    re_str = re_str + "|_[RLrl][0-9]+$|_[RLrl]_|^[RLrl]_|_[RLrl]$"
    re_str = re_str + "|_[RLrl][.]|^[RLrl][.]"
    re_str = re_str + "|_[RLrl][0-9]+[.]|^[RLrl][0-9]+[.]"
    rePattern = re.compile(re_str)

    reMatch = re.search(rePattern, name)
    if reMatch:
        instance = reMatch.group(0)
        if instance.find("R") != -1:
            rep = instance.replace("R", "L")
        elif instance.find("L") != -1:
            rep = instance.replace("L", "R")
        elif instance.find("r") != -1:
            rep = instance.replace("r", "l")
        elif instance.find("l") != -1:
            rep = instance.replace("l", "r")
        name = re.sub(rePattern, rep, name)

    return name
