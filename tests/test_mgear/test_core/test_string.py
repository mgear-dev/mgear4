

def test_normalize(setup_path):
    # mGear imports
    from mgear.core import string
    value = "1234-mgear=string@normalize"
    assert string.normalize(value) == "_1234-mgear_string_normalize"
