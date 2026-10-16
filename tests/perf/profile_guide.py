"""Shifter guide profiling harness.

Times the guide operations on a guide template with mayapy: drawing it
(template import), reading it back from the scene (``setFromHierarchy``),
exporting it to a template dictionary and duplicating its largest component
branch. Reports the times, the guide size and the top cProfile entries of
each operation.

Not a pytest module. Run it with mayapy from the repository root::

    mayapy tests/perf/profile_guide.py biped.sgt
    mayapy tests/perf/profile_guide.py path/to/guide.sgt --no-profile
    mayapy tests/perf/profile_guide.py biped.sgt --out prof_dir
    mayapy tests/perf/profile_guide.py biped.sgt --save-baseline base.json
    mayapy tests/perf/profile_guide.py biped.sgt --baseline base.json

A guide using custom components needs ``MGEAR_SHIFTER_COMPONENT_PATH`` set
to their folder.
"""

import argparse
import json
import os

from profile_build import SCRIPTS
from profile_build import add_common_args
from profile_build import print_stats
from profile_build import run_profiled
from profile_build import start_maya

TEMPLATES = os.path.join(SCRIPTS, "mgear", "shifter", "component", "_templates")
OPERATIONS = ("Draw", "Read", "Export", "Duplicate")


def parse_args(argv=None):
    """Parse the command line arguments.

    Args:
        argv (list of str, optional): Arguments to parse. Defaults to
            ``sys.argv[1:]``.

    Returns:
        argparse.Namespace: The parsed arguments.
    """
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "template",
        nargs="?",
        default="biped.sgt",
        help="Bundled template file name or path of a .sgt file.",
    )
    parser.add_argument("--out", help="Folder to write one .prof file per operation.")
    add_common_args(parser, top=25)
    return parser.parse_args(argv)


def template_path(template):
    """Resolve a bundled template name or a file path.

    Args:
        template (str): Bundled template file name or path of a .sgt file.

    Returns:
        str: Path of the template file.
    """
    if os.path.isfile(template):
        return os.path.abspath(template)
    return os.path.join(TEMPLATES, template)


def largest_branch():
    """Return the left side component root with the most roots below it.

    Left side branches (arm, leg) are what users usually duplicate. Falls
    back to all component roots when the guide has no left side component.

    Returns:
        str: Long name of the component root, or None if the guide has none.
    """
    from maya import cmds

    roots = cmds.ls("guide", dag=True, long=True, type="transform") or []
    roots = [r for r in roots if cmds.attributeQuery("comp_type", node=r, exists=True)]
    left = [r for r in roots if cmds.getAttr(r + ".comp_side") == "L"]
    best = None
    best_count = -1
    for root in left or roots:
        count = sum(1 for r in roots if r.startswith(root + "|"))
        if count > best_count:
            best, best_count = root, count
    return best


def profile_guide(path, profile=True):
    """Draw, read, export and duplicate a guide template in a new scene.

    Args:
        path (str): Path of the guide template file.
        profile (bool, optional): Run the operations under cProfile.

    Returns:
        tuple: (result dict, dict of operation name to cProfile.Profile)
    """
    from maya import cmds

    import mgear
    import mgear.pymaya as pm
    from mgear import shifter
    from mgear.shifter import io

    mgear.log = lambda *args, **kwargs: None

    with open(path) as f:
        conf = json.load(f)

    cmds.file(new=True, force=True)
    times = {}
    profilers = {}

    def record(name, func):
        seconds, profiler, value = run_profiled(func, profile)
        times[name] = seconds
        if profiler:
            profilers[name] = profiler
        return value

    record("Draw", lambda: io.import_guide_template(conf=conf))
    transforms = len(cmds.ls("guide", dag=True, type="transform"))
    nodes = len(cmds.ls())

    rig = shifter.Rig()
    record("Read", lambda: rig.guide.setFromHierarchy(pm.PyNode("guide")))
    record("Export", lambda: rig.guide.get_guide_template_dict())

    branch = largest_branch()
    if branch:
        branch_root = pm.PyNode(branch)
        record("Duplicate", lambda: shifter.Rig().guide.duplicate(branch_root))

    result = {
        "template": os.path.basename(path),
        "maya": cmds.about(version=True),
        "profiled": profile,
        "components": len(rig.guide.componentsIndex),
        "transforms": transforms,
        "nodes": nodes,
        "duplicate_branch": branch.split("|")[-1] if branch else None,
        "times": times,
    }
    return result, profilers


def report(result, baseline=None):
    """Print the guide operations report.

    Args:
        result (dict): Result from ``profile_guide``.
        baseline (dict, optional): An earlier result to compare with.
    """
    print("\n" + "=" * 64)
    print(
        "{template}: {components} components, {transforms} transforms, "
        "{nodes} nodes".format(**result)
    )
    if result["duplicate_branch"]:
        print("Duplicate branch: {}".format(result["duplicate_branch"]))
    print("=" * 64)
    base_times = (baseline or {}).get("times", {})
    for name in OPERATIONS:
        if name not in result["times"]:
            continue
        seconds = result["times"][name]
        line = "  {:<12}{:>8.3f}s".format(name, seconds)
        if name in base_times:
            line += "   {:+.3f}s ({:.0%} of baseline)".format(
                seconds - base_times[name], seconds / base_times[name]
            )
        print(line)


def main(argv=None):
    """Run the harness.

    Args:
        argv (list of str, optional): Command line arguments.

    Returns:
        dict: The result.
    """
    args = parse_args(argv)
    start_maya()
    try:
        result, profilers = profile_guide(
            template_path(args.template), profile=not args.no_profile
        )
        baseline = None
        if args.baseline:
            with open(args.baseline) as f:
                baseline = json.load(f)
        report(result, baseline)

        if args.out:
            os.makedirs(args.out, exist_ok=True)
        for name in OPERATIONS:
            if name not in profilers:
                continue
            print("\n--- {} (sorted by self time)".format(name))
            out = None
            if args.out:
                out = os.path.join(args.out, "{}.prof".format(name.lower()))
            print_stats(profilers[name], args.top, out)
        if args.save_baseline:
            with open(args.save_baseline, "w") as f:
                json.dump(result, f, indent=4)
            print("Baseline written to {}".format(args.save_baseline))
        return result
    finally:
        import maya.standalone

        maya.standalone.uninitialize()


if __name__ == "__main__":
    main()
