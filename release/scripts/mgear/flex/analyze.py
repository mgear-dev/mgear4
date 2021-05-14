""" flex.analyze

flex.analyze module contains functions which allows you analyze the shapes
you want to update with Flex

:module: flex.analyze
"""

# imports
from __future__ import absolute_import
from mgear.flex import logger
from mgear.flex.decorators import timer
from mgear.flex.query import get_matching_shapes_from_group
from mgear.flex.query import get_missing_shapes_from_group
from mgear.flex.query import is_matching_bouding_box
from mgear.flex.query import is_matching_count
from mgear.flex.query import is_matching_type


@timer
def analyze_groups(source, target):
    """ Analyze the shapes found inside the source and target groups

    :param source: maya transform node
    :type source: str

    :param target: maya transform node
    :type target: str
    """

    logger.debug("Analysing the following groups - source: {}  - target: {}"
                 .format(source, target))

    # gets the matching shapes
    matching_shapes = get_matching_shapes_from_group(source, target)

    # gets mismatching shape types
    mismatched_types = [x for x in matching_shapes if not is_matching_type(
        x, matching_shapes[x])]

    # gets mismatching shape vertices count
    mismatched_count = [x for x in matching_shapes if not is_matching_count(
        x, matching_shapes[x])]

    # gets mismatching shape bounding box
    mismatched_bbox = [x for x in matching_shapes if not
                       is_matching_bouding_box(x, matching_shapes[x])]

    logger.info("-" * 90)
    logger.info("Mismatch shapes types: {}".format(mismatched_types))
    logger.info("Mismatch vertices shapes: {}".format(mismatched_count))
    logger.info("Mismatch volume shapes: {}".format(mismatched_bbox))
    logger.warning("-" * 90)
    logger.warning("Source missing shapes: {}" .format(
        get_missing_shapes_from_group(source, target)))
    logger.warning("Target missing shapes: {}" .format(
        get_missing_shapes_from_group(target, source)))
    logger.warning("-" * 90)

    return matching_shapes, mismatched_types, mismatched_count, mismatched_bbox
