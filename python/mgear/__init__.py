
# Set mGear version
__version_info__ = (1, 0, 0)
__version__ = "{}.{}.{}".format(__version_info__[0],
                                __version_info__[1],
                                __version_info__[2])

major, minor, micro = __version_info__
"""mGear version numbers"""
version = __version__
"""mGear version"""
version_info = ("{}(major={},minor={}, micro={})"
                .format(__package__, major, minor, micro))
"""mGear version details"""
