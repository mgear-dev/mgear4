"""mgear.core.string test"""


def test_convert_RL_name(setup_path):
    # mGear imports
    from mgear.core.string import convert_RL_name

    names = {"token_L": "token_R",
             "token_L_token": "token_R_token",
             "token_R_token": "token_L_token",
             "L_token": "R_token",
             "L_token_L_token": "R_tokenR_token",
             "L": "R",
             "R": "L",
             "token": "token"}
    for item in names:
        assert convert_RL_name(item) == names[item]


def test_normalize(setup_path):
    # mGear imports
    from mgear.core.string import normalize

    value = "1234-mgear=string@normalize"
    assert normalize(value) == "_1234-mgear_string_normalize"
    assert normalize(value, True) == "_1234_mgear_string_normalize"


def test_remove_invalid_characters(setup_path):
    # mGear imports
    from mgear.core.string import remove_invalid_characters

    value = "1234-mgear=string@normalize"
    assert remove_invalid_characters(value) == "1234mgearstringnormalize"


def test_replace_sharps_with_padding(setup_path):
    # mGear imports
    from mgear.core.string import replace_sharps_with_padding

    assert replace_sharps_with_padding("value_###", 30) == "value_030"
    assert replace_sharps_with_padding("value", 12) == "value12"
    assert replace_sharps_with_padding("value", 2) == "value2"
    assert replace_sharps_with_padding("value#", 2) == "value2"
    assert replace_sharps_with_padding("value##", 2) == "value02"
