"""Logging Maya data"""


def matrix4(m, msg="matrix4"):
    """Print matrix 4x4 data.

    Arguments:
        m (matrix): 4x4 Matrix
        msg (str): Message in front of the data print.
    """
    s = msg + " : \n"\
        + "| %s , %s , %s , %s |\n" % (m[0][0], m[0][1], m[0][2], m[0][3])\
        + "| %s , %s , %s , %s |\n" % (m[1][0], m[1][1], m[1][2], m[1][3])\
        + "| %s , %s , %s , %s |\n" % (m[2][0], m[2][1], m[2][2], m[2][3])\
        + "| %s , %s , %s , %s |" % (m[3][0], m[3][1], m[3][2], m[3][3])

    print(s)
