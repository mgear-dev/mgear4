"""Placement and slider math of the Animbits Hub.

Plain tuples, no Qt, so it is tested without a window. Points are
``(x, y)``, sizes ``(width, height)`` and rectangles
``(x, y, width, height)``.
"""

STOP_COUNT = 11


def stop_fractions():
    """Return the fractions of the slider stops, 0 to 1 in 10% steps.

    Returns:
        list: The 11 fractions.
    """
    return [i / float(STOP_COUNT - 1) for i in range(STOP_COUNT)]


def fraction_from_x(x, left, width):
    """Return the slider fraction at a position, clamped to [0, 1].

    Args:
        x (float): Position on the slider.
        left (float): Position of the 0% stop.
        width (float): Distance from the 0% to the 100% stop.

    Returns:
        float: The fraction.
    """
    if width <= 0:
        return 0.5
    return min(max((x - left) / float(width), 0.0), 1.0)


def clamp_to_rect(pos, size, rect):
    """Move a box to fit inside a rectangle.

    A box larger than the rectangle sticks to its top-left corner.

    Args:
        pos (tuple): Top-left corner of the box.
        size (tuple): Size of the box.
        rect (tuple): The rectangle.

    Returns:
        tuple: The new top-left corner.
    """
    rx, ry, rw, rh = rect
    x = max(rx, min(pos[0], rx + rw - size[0]))
    y = max(ry, min(pos[1], ry + rh - size[1]))
    return (x, y)


def nearest_rect(pos, rects):
    """Return the rectangle containing a point, or the nearest one.

    Args:
        pos (tuple): The point.
        rects (list): Rectangles, e.g. the available screen areas.

    Returns:
        tuple: The rectangle, or None when ``rects`` is empty.
    """
    best = None
    best_distance = None
    for rect in rects:
        rx, ry, rw, rh = rect
        dx = max(rx - pos[0], 0, pos[0] - (rx + rw - 1))
        dy = max(ry - pos[1], 0, pos[1] - (ry + rh - 1))
        distance = dx * dx + dy * dy
        if best is None or distance < best_distance:
            best = rect
            best_distance = distance
    return best


def place_at_cursor(cursor, anchor, size, screen):
    """Return the top-left corner that puts an anchor under the cursor.

    The box is moved inside the screen when it does not fit.

    Args:
        cursor (tuple): Cursor position.
        anchor (tuple): Point of the box to put under the cursor, relative
            to its top-left corner.
        size (tuple): Size of the box.
        screen (tuple): Available area of the screen under the cursor.

    Returns:
        tuple: The top-left corner.
    """
    pos = (cursor[0] - anchor[0], cursor[1] - anchor[1])
    return clamp_to_rect(pos, size, screen)


def place_fixed(pos, size, screens):
    """Return a fixed top-left corner moved inside the nearest screen.

    Args:
        pos (tuple): The saved top-left corner.
        size (tuple): Size of the box.
        screens (list): Available areas of all screens.

    Returns:
        tuple: The top-left corner.
    """
    rect = nearest_rect(pos, screens)
    if rect is None:
        return pos
    return clamp_to_rect(pos, size, rect)
