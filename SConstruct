import os
import sys
import excons
import excons.config
import excons.tools.maya as maya
import excons.tools.gl as gl

maya.SetupMscver()
env = excons.MakeBaseEnv()

version = (4, 0, 9)
versionstr = "%d.%d.%d" % version
platname = {"win32": "windows", "darwin": "osx"}.get(sys.platform, "linux")
outprefix = "platforms/%s/%s/%s/plug-ins" % (maya.Version(nice=True),
                                             platname, excons.arch_dir)

outdir = excons.OutputBaseDirectory()

gen = excons.config.AddGenerator(
    env, "mgear", {"MGEAR_VERSION": "[%d, %d, %d]" % version,
                   "MGEAR_MAJMIN_VERSION": "%d.%d" % (version[0], version[1]),
                   "MGEAR_VERSION_MAJOR": "%d" % version[0],
                   "MGEAR_VERSION_MINOR": "%d" % version[1],
                   "MGEAR_VERSION_PATCH": "%d" % version[2]})

mgearmod = gen("mGear.mod", "mGear.mod.in")
mgearpy = filter(lambda x: not os.path.basename(x).startswith(
    "__init__.py"), excons.glob("scripts/mgear/*"))
qtpy = ["vendor/Qtdotpy/Qt.py"]
qjason = ["vendor/QJsonModel/qjsonmodel.py"]
NoClean(mgearmod)

defines = []
if sys.platform == "win32":
    defines.append("NOMINMAX")


def maya_math_nodes_setup(env):
    env.Append(CPPDEFINES=[('NODE_NAME_PREFIX', '\"\\\"math_\\\"\"')])
    env.Append(CCFLAGS=["-Os"])
    env.Append(CPPFLAGS=" -DPROJECT_VERSION=\"\\\"1.4.0\\\"\"")


def CVWrapSetup(env):
    if sys.platform == "win32":
        env.Append(CCFLAGS=["/arch:AVX"])
    else:
        env.Append(CCFLAGS=["-mavx"])


targets = [
    {
        "name": "mgear_core",
        "type": "install",
        "desc": "mgear core python modules",
        "install": {"scripts/mgear/vendor": qjason + qtpy,
                    "": mgearmod}
    },
    {
        "name": "mgear_solvers",
        "type": "dynamicmodule",
        "desc": "mgear solvers plugin",
        "prefix": outprefix,
        "bldprefix": maya.Version(),
        "ext": maya.PluginExt(),
        "defs": defines,
        "incdirs": ["plugins/mgear_solvers/src"],
        "srcs": excons.glob("src/*.cpp"),
        "custom": [maya.Require]
    },
    {
        "name": "twist_spline",
        "type": "dynamicmodule",
        "desc": "twist spline plugin",
        "prefix": outprefix,
        "bldprefix": maya.Version(),
        "ext": maya.PluginExt(),
        "defs": defines,
        "incdirs": ["vendor/TwistSpline"],
        "srcs": excons.glob("vendor/TwistSpline/*.cpp"),
        "custom": [maya.Require, gl.Require]
    },
    {
        "name": "cvwrap",
        "type": "dynamicmodule",
        "desc": "wrap deformer plugin",
        "prefix": outprefix,
        "bldprefix": maya.Version(),
        "ext": maya.PluginExt(),
        "defs": defines,
        "incdirs": ["src"],
        "srcs": excons.glob("vendor/cvwrap/src/*.cpp"),
        "custom": [maya.Require, CVWrapSetup],
        "libs": ([] if maya.Version(asString=False) < 201600 else ["clew"]),
        "install": {"scripts": excons.glob("vendor/cvwrap/scripts/*")}
    },
    {
        "name": "maya-math-nodes",
        "type": "dynamicmodule",
        "desc": "math nodes plugin",
        "prefix": outprefix,
        "bldprefix": maya.Version(),
        "ext": maya.PluginExt(),
        "defs": defines,
        "incdirs": ["vendor/maya-math-node"],
        "srcs": excons.glob("vendor/maya-math-nodes/src/*.cpp"),
        "custom": [maya.Require, maya_math_nodes_setup]
    },
    {
        "name": "grim_IK",
        "type": "dynamicmodule",
        "desc": "grim IK solver",
        "prefix": outprefix,
        "bldprefix": maya.Version(),
        "ext": maya.PluginExt(),
        "defs": defines,
        "incdirs": ["vendor/grim_IK"],
        "srcs": excons.glob("vendor/grim_IK/*.cpp"),
        "custom": [maya.Require]
    },
    {
        "name": "weightDriver",
        "type": "dynamicmodule",
        "desc": "weightDriver node",
        "prefix": outprefix,
        "bldprefix": maya.Version(),
        "ext": maya.PluginExt(),
        "defs": defines,
        "incdirs": ["vendor/weightDriver"],
        "srcs": excons.glob("vendor/weightDriver/source/*.cpp"),
        "custom": [maya.Require, gl.Require],
        "install": {"scripts": excons.glob(
            "vendor/weightDriver/modules/weightDriver/scripts/*")}
    }
]

excons.AddHelpTargets(
    mgear="mgear maya framework"
    " (mgear_core, mgear_solvers, cvwrap, grim_IK, maya-math-nodes)")

td = excons.DeclareTargets(env, targets)

env.Alias("mgear", [td["mgear_core"], td["twist_spline"], td["mgear_solvers"],
                    td["cvwrap"], td["grim_IK"], td["maya-math-nodes"],
                    td["weightDriver"]])

td["python"] = filter(lambda x: os.path.splitext(
    str(x))[1] != ".mel", Glob(outdir + "scripts/*"))
td["scripts"] = Glob(outdir + "scripts/*.mel")

pluginsdir = "/plug-ins/%s/%s" % (maya.Version(nice=True),
                                  excons.EcosystemPlatform())

ecodirs = {"mgear_solvers": pluginsdir,
           "twist_spline": pluginsdir,
           "cvwrap": pluginsdir,
           "grim_IK": pluginsdir,
           "maya-math-nodes": pluginsdir,
           "weightDriver": pluginsdir,
           "python": "/python",
           "scripts": "/scripts"}

excons.EcosystemDist(env, "mgear.env", ecodirs, version=versionstr, targets=td)

Default(["mgear"])
