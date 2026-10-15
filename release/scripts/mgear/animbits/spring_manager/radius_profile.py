"""Radius profile math of chain springs (pure Python, no Maya).

A radius profile is one factor per chain joint, multiplying the root to
tip radius gradient. Joints are opaque hashable ids; a chain is given as
sections, ``(start joint, end joint, ratio, end ratio)`` tuples, the
ratios going from 0 at the root to 1 at the tips.
"""

SMOOTH = 2
FACTOR_MIN = 0.01
FACTOR_MAX = 100.0


def profile_paths(sections):
    """Split chain sections into root-to-leaf paths.

    Args:
        sections (list): ``(start joint, end joint, ...)`` tuples.

    Returns:
        list: Paths, each a list of section indices from a root to a leaf.
    """
    ends = {section[1] for section in sections}
    leaving = {}
    for index, section in enumerate(sections):
        leaving.setdefault(section[0], []).append(index)
    paths = []
    stack = [
        [index] for index, section in enumerate(sections) if section[0] not in ends
    ]
    while stack:
        path = stack.pop()
        children = leaving.get(sections[path[-1]][1])
        if children:
            stack.extend(path + [child] for child in reversed(children))
        else:
            paths.append(path)
    return paths


def chain_joints(sections):
    """Return the joints of chain sections with their ratios, in order.

    Args:
        sections (list): ``(start joint, end joint, ratio, end ratio)``.

    Returns:
        list: ``(joint, ratio)`` pairs, each joint once.
    """
    joints = {}
    for start, end, ratio, end_ratio in sections:
        joints.setdefault(start, ratio)
        joints.setdefault(end, end_ratio)
    return list(joints.items())


def smooth_values(values, passes=SMOOTH):
    """Smooth values with a 1-2-1 moving average, the ends kept in place.

    Args:
        values (list): Numbers, in order.
        passes (int, optional): Number of passes, 0 for none.

    Returns:
        list: The smoothed values.
    """
    values = list(values)
    for _ in range(passes):
        if len(values) < 3:
            break
        values = (
            [(2.0 * values[0] + values[1]) / 3.0]
            + [
                (values[index - 1] + 2.0 * values[index] + values[index + 1]) / 4.0
                for index in range(1, len(values) - 1)
            ]
            + [(values[-2] + 2.0 * values[-1]) / 3.0]
        )
    return values


def sample_at(samples, ratio):
    """Return the value of sorted samples at a ratio, linearly interpolated.

    Args:
        samples (list): ``(ratio, value)`` pairs sorted by ratio.
        ratio (float): Ratio to read.

    Returns:
        float: The value, clamped to the first and last samples.
    """
    if ratio <= samples[0][0]:
        return samples[0][1]
    for (x0, y0), (x1, y1) in zip(samples, samples[1:]):
        if ratio <= x1:
            if x1 - x0 < 1e-9:
                return y1
            return y0 + (y1 - y0) * (ratio - x0) / (x1 - x0)
    return samples[-1][1]


def joint_radii(sections, samples, passes=SMOOTH):
    """Return a radius per joint from samples measured along the sections.

    The samples are smoothed along each root-to-leaf path on its own, so
    branches are never averaged together. A joint on several paths (a
    branch pivot, the joints before it) gets the mean of their estimates.

    Args:
        sections (list): ``(start joint, end joint, ratio, end ratio)``.
        samples (list): Per section, ``(ratio, radius)`` measures.
        passes (int, optional): Smoothing passes.

    Returns:
        dict: ``{joint: radius}``, without the joints of paths that have
        no samples.
    """
    estimates = {}
    for path in profile_paths(sections):
        points = sorted(point for index in path for point in samples[index])
        if not points:
            continue
        values = smooth_values([value for _, value in points], passes)
        points = list(zip([ratio for ratio, _ in points], values))
        for joint, ratio in chain_joints([sections[index] for index in path]):
            estimates.setdefault(joint, []).append(sample_at(points, ratio))
    return {joint: sum(values) / len(values) for joint, values in estimates.items()}


def gradient(root, tip, ratio):
    """Return the root to tip radius gradient at a ratio.

    Args:
        root (float): Root radius.
        tip (float): Tip radius.
        ratio (float): 0 at the root, 1 at the tip.

    Returns:
        float: The radius.
    """
    return root + (tip - root) * ratio


def factor(radius, line_value):
    """Return the profile factor turning a gradient value into a radius.

    Args:
        radius (float): Wanted radius.
        line_value (float): Gradient value at the joint.

    Returns:
        float: ``radius / line_value``, clamped to the factor range.
    """
    if line_value <= 1e-9:
        return 1.0
    return max(FACTOR_MIN, min(FACTOR_MAX, radius / line_value))


def resample(items, joints):
    """Map stored profile items onto the joints of a chain.

    Joints are matched by id first. The others take the factors
    interpolated at their ratio, items at the same ratio averaged.

    Args:
        items (list): ``(joint, ratio, factor)`` stored items.
        joints (list): ``(joint, ratio)`` of the target chain.

    Returns:
        dict: ``{joint: factor}``, empty without items.
    """
    if not items:
        return {}
    by_joint = {joint: value for joint, _, value in items}
    by_ratio = {}
    for _, ratio, value in items:
        by_ratio.setdefault(round(ratio, 6), []).append(value)
    samples = sorted(
        (ratio, sum(values) / len(values)) for ratio, values in by_ratio.items()
    )
    return {
        joint: by_joint[joint] if joint in by_joint else sample_at(samples, ratio)
        for joint, ratio in joints
    }
