from maya import cmds

print(r"""
 ____________________________________
|             _____                  |
|            / ____|                 |
|  _ __ ___ | |  __  ___  __ _ _ __  |
| | '_ ` _ \| | |_ |/ _ \/ _` | '__| |
| | | | | | | |__| |  __/ (_| | |    |
| |_| |_| |_|\_____|\___|\__,_|_|    |
|____________________________________|

""")


if not cmds.about(batch=True):
    from pymel import mayautils
    import mgear.menu
    mayautils.executeDeferred(mgear.menu.install_main_menu)
