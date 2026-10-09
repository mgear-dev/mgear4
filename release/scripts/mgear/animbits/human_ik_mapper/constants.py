"""HumanIK Mapper constants: bone groups, names and file format."""

CHAR_NAME = "MGearIKHuman"
# tag on the HumanIK character created by the mapper
CHARACTER_TAG = "hikMapperCharacter"
REFERENCE = "Reference"

# message attribute linking a mapped control to its Sub IK controls
SUB_IK_ATTR = "sub_ik"
# tag on the parent constraints the mapper creates on Sub IK controls
SUB_IK_CONSTRAINT_TAG = "hikMapperSubIk"

FILE_VERSION = 2
MAPPING_FILTER = "HumanIK Mapping (*.hikm)"
BATCH_FILTER = "Batch Bake List (*.bkcn)"
SOURCE_FILTER = "Animation Files (*.fbx *.ma *.mb)"

HEAD = (
    "Head",
    "Neck",
    "Neck1",
    "Neck2",
    "Neck3",
    "Neck4",
    "Neck5",
    "Neck6",
    "Neck7",
    "Neck8",
    "Neck9",
)
SPINE = (
    "Hips",
    "Spine",
    "Spine1",
    "Spine2",
    "Spine3",
    "Spine4",
    "Spine5",
    "Spine6",
    "Spine7",
    "Spine8",
    "Spine9",
)
LEFT_ARM = ("LeftShoulder", "LeftArm", "LeftForeArm", "LeftHand")
LEFT_UPPER_ARM_ROLLS = tuple("LeafLeftArmRoll{}".format(i) for i in range(1, 6))
LEFT_LOWER_ARM_ROLLS = tuple("LeafLeftForeArmRoll{}".format(i) for i in range(1, 6))
LEFT_HAND = tuple(
    "LeftHand{}{}".format(finger, i)
    for finger in ("Thumb", "Index", "Middle", "Ring", "Pinky")
    for i in range(1, 4)
)
LEFT_LEG = ("LeftUpLeg", "LeftLeg", "LeftFoot", "LeftToeBase")
LEFT_UPPER_LEG_ROLLS = tuple("LeafLeftUpLegRoll{}".format(i) for i in range(1, 6))
LEFT_LOWER_LEG_ROLLS = tuple("LeafLeftLegRoll{}".format(i) for i in range(1, 6))


def mirror_bone(bone):
    """Return the HumanIK bone of the opposite side.

    Args:
        bone (str): HumanIK bone name, e.g. ``LeafLeftArmRoll1``.

    Returns:
        str: The opposite bone, or None for center bones.
    """
    if "Left" in bone:
        return bone.replace("Left", "Right")
    if "Right" in bone:
        return bone.replace("Right", "Left")
    return None


def _right(bones):
    return tuple(mirror_bone(bone) for bone in bones)


# the bones HumanIK needs to solve a character
REQUIRED_BONES = frozenset(
    ("Hips", "Spine", "Head")
    + tuple(
        side + bone
        for side in ("Left", "Right")
        for bone in ("UpLeg", "Leg", "Foot", "Arm", "ForeArm", "Hand")
    )
)


def is_required(bone):
    """Return True for the bones HumanIK needs to solve a character.

    Args:
        bone (str): HumanIK bone name.

    Returns:
        bool: True if the bone is in :data:`REQUIRED_BONES`.
    """
    return bone in REQUIRED_BONES


# HumanIK bones of each body part, by key
BODY_PART_BONES = {
    "head": HEAD,
    "spine": SPINE,
    "left_arm": LEFT_ARM,
    "right_arm": _right(LEFT_ARM),
    "left_upper_arm_rolls": LEFT_UPPER_ARM_ROLLS,
    "left_lower_arm_rolls": LEFT_LOWER_ARM_ROLLS,
    "right_upper_arm_rolls": _right(LEFT_UPPER_ARM_ROLLS),
    "right_lower_arm_rolls": _right(LEFT_LOWER_ARM_ROLLS),
    "left_hand": LEFT_HAND,
    "right_hand": _right(LEFT_HAND),
    "left_leg": LEFT_LEG,
    "right_leg": _right(LEFT_LEG),
    "left_upper_leg_rolls": LEFT_UPPER_LEG_ROLLS,
    "left_lower_leg_rolls": LEFT_LOWER_LEG_ROLLS,
    "right_upper_leg_rolls": _right(LEFT_UPPER_LEG_ROLLS),
    "right_lower_leg_rolls": _right(LEFT_LOWER_LEG_ROLLS),
}

STATUS_EMPTY = "empty"
STATUS_PARTIAL = "partial"
STATUS_COMPLETE = "complete"
