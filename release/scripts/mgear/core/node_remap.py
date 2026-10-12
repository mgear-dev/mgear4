"""Find and match Maya nodes by name across namespaces and DAG paths.

Generic helpers used by IO tools (skin, curves, anim...) to resolve
exported node names against the current scene, and to propose matches
for missing nodes. Matchers are pure Python and return ``{source: target}``
proposals; callers decide how to combine or apply them.
"""

import difflib
import logging
import re

from maya import cmds

from mgear.core import string

logger = logging.getLogger(__name__)


def strip_namespace_path(path):
    """Remove the namespace from every segment of a DAG path.

    Args:
        path (str): Node name or DAG path, e.g. ``|a:grp|a:b:body``.

    Returns:
        str: The path without namespaces, e.g. ``|grp|body``.
    """
    return "|".join(seg.split(":")[-1] for seg in path.split("|"))


def leaf_name(path):
    """Return the leaf name of a DAG path, namespace kept.

    Args:
        path (str): Node name or DAG path.

    Returns:
        str: The leaf name, e.g. ``a:body`` for ``|grp|a:body``.
    """
    return path.split("|")[-1]


def short_name(path):
    """Return the namespace-stripped leaf name of a DAG path.

    Args:
        path (str): Node name or DAG path.

    Returns:
        str: The leaf name without namespace.
    """
    return strip_namespace_path(path).split("|")[-1]


def split_component(name):
    """Split a node or component name into the node and the component.

    Component ranges hold colons (``f[0:10]``), so read namespaces from
    the node part only.

    Args:
        name (str): Node, DAG path or component, e.g. ``|grp|ns:body.f[0:10]``.

    Returns:
        tuple: ``(node leaf name, component)``, e.g.
            ``("ns:body", ".f[0:10]")``; the component is ``""`` for a node.
    """
    leaf = leaf_name(name)
    if "." in leaf:
        node, component = leaf.split(".", 1)
        return node, "." + component
    return leaf, ""


def swap_namespace(name, namespace):
    """Move a node or component name to another namespace.

    Args:
        name (str): Node or component, e.g. ``chrA:body.f[0:10]``.
        namespace (str): New namespace, ``""`` or None for the root.

    Returns:
        str: E.g. ``chrB:body.f[0:10]``, the component kept.
    """
    node, component = split_component(name)
    return add_namespace(short_name(node), namespace) + component


def scene_namespaces():
    """Return the namespaces of the scene, nested ones included.

    Maya's own ``UI`` and ``shared`` namespaces are left out.

    Returns:
        list: Sorted namespace names, without leading colon.
    """
    namespaces = (
        cmds.namespaceInfo(
            ":", listOnlyNamespaces=True, recurse=True, absoluteName=True
        )
        or []
    )
    names = [ns.lstrip(":") for ns in namespaces]
    return sorted(ns for ns in names if ns and ns not in ("UI", "shared"))


def get_namespace(path):
    """Return the namespace of a node name or DAG path leaf.

    Args:
        path (str): Node name or DAG path, e.g. ``|grp|chr:sub:arm_ctl``.

    Returns:
        str: The namespace with a trailing colon, e.g. ``"chr:sub:"``, or
        ``""`` for the root namespace.
    """
    leaf = leaf_name(path)
    if ":" not in leaf:
        return ""
    return leaf.rsplit(":", 1)[0] + ":"


def add_namespace(name, namespace):
    """Return a short name placed in a namespace.

    Args:
        name (str): Node name without namespace.
        namespace (str): Namespace, with or without trailing colon. ``""``
            or None for the root namespace.

    Returns:
        str: ``namespace:name``, or ``name`` for the root namespace.
    """
    namespace = (namespace or "").rstrip(":")
    return "{}:{}".format(namespace, name) if namespace else name


def common_namespace(paths):
    """Return the namespace shared by node names, e.g. a selection.

    Args:
        paths (list): Node names or DAG paths.

    Returns:
        tuple: ``(namespace, candidates)``. ``namespace`` (trailing colon,
        ``""`` for the root namespace) when every name is in the same
        namespace, None when there are no names or several namespaces.
        ``candidates`` is the sorted list of unique namespaces.
    """
    candidates = sorted({get_namespace(path) for path in paths})
    if len(candidates) == 1:
        return candidates[0], candidates
    return None, candidates


def _ls(patterns, node_type=None, recursive=False):
    """List unique long names matching the patterns, ignoring bad patterns.

    Args:
        patterns (list): Name patterns for ``cmds.ls``.
        node_type (str, optional): Node type filter.
        recursive (bool, optional): Search in all namespaces.

    Returns:
        list: Unique full DAG paths (or node names for DG nodes).
    """
    kwargs = {"long": True}
    if node_type:
        kwargs["type"] = node_type
    if recursive:
        kwargs["recursive"] = True
    try:
        found = cmds.ls(*patterns, **kwargs) or []
    except (RuntimeError, ValueError):
        return []
    return list(dict.fromkeys(found))


def filter_by_path_suffix(paths, suffix):
    """Keep the paths whose namespace-stripped segments end with the suffix.

    Args:
        paths (list): Full DAG paths.
        suffix (str): Namespace-stripped partial or full path.

    Returns:
        list: The matching paths.
    """
    suffix_parts = [p for p in suffix.split("|") if p]
    if not suffix_parts:
        return list(paths)
    count = len(suffix_parts)
    return [
        p
        for p in paths
        if [s for s in strip_namespace_path(p).split("|") if s][-count:] == suffix_parts
    ]


def find_node_candidates(name, long_name=None, node_type=None, namespace=None):
    """Find the scene nodes that match an exported node name.

    The lookup stops at the first step that finds exactly one node:

    1. ``namespace`` remap of the stripped short name (if given).
    2. Exact name.
    3. ``long_name`` (or ``name`` if it is a partial path), namespaces
       stripped, matched as a path suffix.
    4. Stripped short name in any namespace.

    Args:
        name (str): Exported node name, may include namespace or path.
        long_name (str, optional): Exported full DAG path, used to
            disambiguate clashing short names.
        node_type (str, optional): Only return nodes of this type.
        namespace (str, optional): Force this namespace, e.g. ``"char:"``.
            Use ``""`` for the root namespace.

    Returns:
        list: Full paths. One item if resolved, several if ambiguous,
            empty if nothing matches.
    """
    leaf = short_name(name)

    if namespace is not None:
        ns = namespace.strip(":")
        target = "{}:{}".format(ns, leaf) if ns else leaf
        hits = _ls([target], node_type)
        if hits:
            return hits

    hits = _ls([name], node_type)
    if len(hits) == 1:
        return hits

    pool = _ls([leaf], node_type, recursive=True)
    if len(pool) <= 1:
        return pool

    suffix = long_name or (name if "|" in name else None)
    if suffix:
        matched = filter_by_path_suffix(pool, strip_namespace_path(suffix))
        if matched:
            return matched

    return pool


def find_node(name):
    """Find the single scene node matching an exported node name.

    Uses :func:`find_node_candidates`. When several nodes match, the name
    is ambiguous: a warning is logged and None is returned.

    Args:
        name (str): Exported node name, may include namespace or path.

    Returns:
        str: Full path of the node, or None if not found or ambiguous.
    """
    if not name:
        return None
    hits = find_node_candidates(name)
    if len(hits) > 1:
        logger.warning("Ambiguous name '%s' (%d matches).", name, len(hits))
    return hits[0] if len(hits) == 1 else None


def group_by_short_name(paths):
    """Group node names or paths by namespace-stripped short name.

    Args:
        paths (list): Node names or DAG paths.

    Returns:
        dict: ``{short name: [paths]}``
    """
    index = {}
    for path in paths:
        index.setdefault(short_name(path), []).append(path)
    return index


def _unique_by_name(targets):
    """Index targets by namespace-stripped short name, dropping duplicates.

    Args:
        targets (list): Target node names or paths.

    Returns:
        dict: ``{short_name: target}`` for short names that are unique.
    """
    return {
        key: paths[0]
        for key, paths in group_by_short_name(targets).items()
        if len(paths) == 1
    }


def _match_by_rename(sources, targets, rename):
    """Propose matches by renaming each source and looking up the result.

    Args:
        sources (list): Source names to match.
        targets (list): Candidate target names or paths.
        rename (callable): Takes a namespace-stripped short name and
            returns the expected target short name.

    Returns:
        dict: ``{source: target}`` for sources with exactly one match.
    """
    index = _unique_by_name(targets)
    result = {}
    for source in sources:
        target = index.get(rename(short_name(source)))
        if target is not None:
            result[source] = target
    return result


def match_by_pattern(sources, targets, search, replace, regex=False):
    """Propose matches by applying a search/replace to source names.

    Args:
        sources (list): Source names to match.
        targets (list): Candidate target names or paths.
        search (str): Text or regex pattern to search for.
        replace (str): Replacement text.
        regex (bool, optional): Treat ``search`` as a regular expression.

    Returns:
        dict: ``{source: target}`` for sources with exactly one match.
    """
    if regex:
        pattern = re.compile(search)
        return _match_by_rename(
            sources, targets, lambda name: pattern.sub(replace, name)
        )
    return _match_by_rename(
        sources, targets, lambda name: name.replace(search, replace)
    )


def match_by_prefix(sources, targets, strip="", add=""):
    """Propose matches by stripping and/or adding a name prefix.

    Args:
        sources (list): Source names to match.
        targets (list): Candidate target names or paths.
        strip (str, optional): Prefix removed from source names.
        add (str, optional): Prefix added to source names.

    Returns:
        dict: ``{source: target}`` for sources with exactly one match.
    """
    search = "^" + re.escape(strip)
    return match_by_pattern(sources, targets, search, add, regex=True)


def match_by_side_swap(sources, targets):
    """Propose matches by swapping L/R side tokens in source names.

    Uses the mGear mirror naming rules, see ``string.convertRLName``.

    Args:
        sources (list): Source names to match.
        targets (list): Candidate target names or paths.

    Returns:
        dict: ``{source: target}`` for sources with exactly one match.
    """
    return _match_by_rename(sources, targets, string.convertRLName)


def match_by_similarity(sources, targets, cutoff=0.8):
    """Propose the most similar target name for each source.

    Args:
        sources (list): Source names to match.
        targets (list): Candidate target names or paths.
        cutoff (float, optional): Minimum similarity ratio, 0 to 1.

    Returns:
        dict: ``{source: target}`` for sources with a match over the cutoff.
    """
    index = _unique_by_name(targets)
    names = list(index)
    result = {}
    for source in sources:
        close = difflib.get_close_matches(short_name(source), names, n=1, cutoff=cutoff)
        if close:
            result[source] = index[close[0]]
    return result


def similar_names(name, targets, count=5, cutoff=0.6):
    """Return the targets whose short name is most similar to a name.

    Args:
        name (str): Name to compare, may include namespace or path.
        targets (list): Candidate target names or paths.
        count (int, optional): Maximum number of results.
        cutoff (float, optional): Minimum similarity ratio, 0 to 1.

    Returns:
        list: Targets, most similar first. Targets sharing a short name
            are all included.
    """
    index = group_by_short_name(targets)
    close = difflib.get_close_matches(
        short_name(name), list(index), n=count, cutoff=cutoff
    )
    return [target for key in close for target in index[key]][:count]


def match_by_position(source_positions, target_positions, tolerance=0.01):
    """Propose the nearest target for each source by world position.

    Args:
        source_positions (dict): ``{source: (x, y, z)}``.
        target_positions (dict): ``{target: (x, y, z)}``.
        tolerance (float, optional): Maximum distance in world units.

    Returns:
        dict: ``{source: target}`` for sources with a target in tolerance.
    """
    max_dist_sq = tolerance * tolerance
    result = {}
    for source, src_pos in source_positions.items():
        if not src_pos:
            continue
        best = None
        best_dist_sq = max_dist_sq
        sx, sy, sz = src_pos
        for target, (tx, ty, tz) in target_positions.items():
            dist_sq = (sx - tx) ** 2 + (sy - ty) ** 2 + (sz - tz) ** 2
            if dist_sq <= best_dist_sq:
                best = target
                best_dist_sq = dist_sq
        if best is not None:
            result[source] = best
    return result


def flat_name(path):
    """Return a node name usable as a prefix: leaf name, colons replaced.

    Args:
        path (str): Node name or DAG path, e.g. ``"|grp|chr:arm_ctl"``.

    Returns:
        str: ``"chr_arm_ctl"``.
    """
    return leaf_name(path).replace(":", "_")


def match_nodes(sources, targets):
    """Match stored node names to the nodes they are pasted on.

    Used to paste stored data (a pose, world matrices...) on the
    selection, e.g. on another character:

    1. No targets: each source that exists in the scene maps to itself.
    2. Each target takes the first unused source with the same leaf name,
       namespace included.
    3. Remaining targets take the first unused source with the same
       namespace-stripped short name.
    4. Only when steps 2 and 3 matched nothing, sources and targets are
       paired by index, up to the shorter list.

    Targets left without a source in steps 2 and 3 stay unmatched.

    Args:
        sources (list): Stored node names, in the order they were stored.
        targets (list): Scene nodes to paste on, e.g. the selection.

    Returns:
        dict: ``{source: target}``.
    """
    if not targets:
        return {source: source for source in sources if cmds.objExists(source)}

    by_leaf = {}
    by_short = {}
    for source in sources:
        by_leaf.setdefault(leaf_name(source), []).append(source)
        by_short.setdefault(short_name(source), []).append(source)

    result = {}
    used = set()

    def take(index, key):
        for source in index.get(key, ()):
            if source not in used:
                used.add(source)
                return source
        return None

    pending = []
    for target in targets:
        source = take(by_leaf, leaf_name(target))
        if source is None:
            pending.append(target)
        else:
            result[source] = target
    for target in pending:
        source = take(by_short, short_name(target))
        if source is not None:
            result[source] = target
    if result:
        return result
    return dict(zip(sources, targets))
