"""Chain trees for chain springs (pure logic, no Maya).

A chain tree is built from root controls by walking their child
controls. :func:`plan` turns a tree into the proxy joints to build, the
simulated sections (bone -> end, one solver node each) and the joints
each control follows.

Joint keys::

    ("bone", ctl)          bone of a control with at most one child
    ("pivot", ctl)         end joint of a branch control, under its parent
    ("branch", ctl, i)     bone of branch i of a branch control
    ("tip", ctl)           tip after a leaf control

A branch control (several child controls) gets a pivot, ending the
parent's section, and one branch bone per child under the pivot, so each
branch is simulated on its own.
"""

from collections import namedtuple

KINEMATIC = "kinematic"
AVERAGE = "average"
PRIMARY = "primary"
BRANCH_POLICIES = (KINEMATIC, AVERAGE, PRIMARY)

JointSpec = namedtuple("JointSpec", ("key", "parent", "control", "aim"))
Section = namedtuple("Section", ("bone", "end", "control", "ratio", "end_ratio"))


class ChainNode(object):
    """A control in a chain tree.

    Attributes:
        name (str): Control name.
        children (list): Child :class:`ChainNode` items.
        parent (ChainNode): Parent node, None for the root.
    """

    def __init__(self, name, parent=None):
        self.name = name
        self.parent = parent
        self.children = []

    def __repr__(self):
        return "ChainNode({!r})".format(self.name)

    @property
    def is_branch(self):
        """bool: True with several child controls."""
        return len(self.children) > 1

    def walk(self):
        """Yield the node and its descendants, depth first.

        Yields:
            ChainNode: Nodes in tree order.
        """
        yield self
        for child in self.children:
            for node in child.walk():
                yield node


def build_tree(root, children_fn, exclude=None):
    """Build a chain tree from a root control.

    Args:
        root (str): Root control.
        children_fn (callable): ``children_fn(name)`` returns the child
            controls of a control, in order.
        exclude (set, optional): Controls left out, with their descendants.

    Returns:
        ChainNode: The root node.
    """
    exclude = set(exclude or ())
    node = ChainNode(root)
    stack = [node]
    while stack:
        current = stack.pop()
        for child in children_fn(current.name):
            if child in exclude:
                continue
            child_node = ChainNode(child, current)
            current.children.append(child_node)
            stack.append(child_node)
    return node


def split_branches(tree):
    """Return the sub-trees of a tree split at its first branch control.

    The trunk (root to the first branch control, included) is kept in the
    first item when it has more than one control. Each branch becomes a
    tree starting at the branch control's child.

    Args:
        tree (ChainNode): The root node.

    Returns:
        list: :class:`ChainNode` roots (new nodes, the tree is unchanged).
    """
    trees = []
    node = tree
    trunk = ChainNode(tree.name)
    copy = trunk
    while len(node.children) == 1:
        node = node.children[0]
        copy.children.append(ChainNode(node.name, copy))
        copy = copy.children[0]
    if not node.is_branch:
        return [trunk]
    if trunk.children:
        trees.append(trunk)
    for child in node.children:
        trees.append(_copy(child, None))
    return trees


def _copy(node, parent):
    copy = ChainNode(node.name, parent)
    copy.children = [_copy(child, copy) for child in node.children]
    return copy


def _end_key(node):
    """Return the joint key ending the section that reaches a node."""
    return ("pivot", node.name) if node.is_branch else ("bone", node.name)


def plan(tree, policy=KINEMATIC, primary=0):
    """Plan the proxy joints, sections and control drivers of a tree.

    Args:
        tree (ChainNode): The root node.
        policy (str, optional): Branch-root policy, one of
            :data:`BRANCH_POLICIES`.
        primary (int, optional): Branch index followed with the
            ``primary`` policy.

    Returns:
        tuple: ``(joints, sections, drivers)``.

        - ``joints``: :class:`JointSpec` list, parents first. ``control``
          is the control the joint is placed at (the leaf control for
          tips), ``aim`` the control or ``"tip"`` it points to, or None.
        - ``sections``: :class:`Section` list. ``ratio`` is the ratio of
          the section's start joint and ``end_ratio`` the ratio of its end
          joint. A joint's ratio is its depth along the longest path
          through it (counted in sections), 0 at the root and 1 at the
          tips, so a section ends at the ratio its child sections start.
        - ``drivers``: ``{control: [joint keys]}``, the joints each
          control follows (several for the ``average`` policy).

    Raises:
        ValueError: If the policy is unknown.
    """
    if policy not in BRANCH_POLICIES:
        raise ValueError("Unknown branch policy: {}".format(policy))
    joints = []
    sections = []
    drivers = {}
    depth_below = _depth_below(tree)

    def joint_ratio(node, depth):
        return _ratio(depth, depth + depth_below[node.name])

    def add(node, parent_key, depth):
        ratio = joint_ratio(node, depth)
        if node.is_branch:
            pivot = ("pivot", node.name)
            joints.append(JointSpec(pivot, parent_key, node.name, None))
            branches = []
            for index, child in enumerate(node.children):
                key = ("branch", node.name, index)
                branches.append(key)
                joints.append(JointSpec(key, pivot, node.name, child.name))
                sections.append(
                    Section(
                        key,
                        _end_key(child),
                        node.name,
                        ratio,
                        joint_ratio(child, depth + 1),
                    )
                )
                add(child, key, depth + 1)
            if policy == AVERAGE:
                drivers[node.name] = branches
            elif policy == PRIMARY:
                drivers[node.name] = [branches[min(primary, len(branches) - 1)]]
            else:
                drivers[node.name] = [pivot]
            return
        bone = ("bone", node.name)
        child = node.children[0] if node.children else None
        joints.append(
            JointSpec(bone, parent_key, node.name, child.name if child else "tip")
        )
        drivers[node.name] = [bone]
        if child:
            sections.append(
                Section(
                    bone,
                    _end_key(child),
                    node.name,
                    ratio,
                    joint_ratio(child, depth + 1),
                )
            )
            add(child, bone, depth + 1)
        else:
            tip = ("tip", node.name)
            joints.append(JointSpec(tip, bone, node.name, None))
            sections.append(Section(bone, tip, node.name, ratio, 1.0))

    add(tree, None, 0)
    return joints, sections, drivers


def _depth_below(tree):
    """Return the number of sections below each node, along the longest path.

    Args:
        tree (ChainNode): The root node.

    Returns:
        dict: ``{control: sections from the node to its farthest tip}``.
    """
    depths = {}

    def visit(node):
        if not node.children:
            depths[node.name] = 1
        else:
            depths[node.name] = 1 + max(visit(child) for child in node.children)
        return depths[node.name]

    visit(tree)
    return depths


def _ratio(depth, total):
    return float(depth) / total if total else 0.0


def tree_to_data(tree):
    """Return a JSON friendly description of a tree.

    Args:
        tree (ChainNode): The root node.

    Returns:
        dict: ``{"name": control, "children": [...]}``.
    """
    return {
        "name": tree.name,
        "children": [tree_to_data(child) for child in tree.children],
    }


def tree_from_data(data, rename=None, parent=None):
    """Return a tree from :func:`tree_to_data` output.

    Args:
        data (dict): Tree description.
        rename (callable, optional): Maps stored names to scene names.
        parent (ChainNode, optional): Parent node, for recursion.

    Returns:
        ChainNode: The root node.
    """
    name = rename(data["name"]) if rename else data["name"]
    node = ChainNode(name, parent)
    node.children = [
        tree_from_data(child, rename, node) for child in data.get("children") or []
    ]
    return node


def rename_tree_data(data, rename):
    """Return tree data with renamed controls.

    Args:
        data (dict): Tree data from :func:`tree_to_data`.
        rename (callable): Maps a control name to a new name.

    Returns:
        dict: The renamed tree data, or the input when empty.
    """
    if not data:
        return data
    return {
        "name": rename(data["name"]),
        "children": [rename_tree_data(child, rename) for child in data["children"]],
    }
