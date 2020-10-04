

def test_mgear_version(setup_path):
    # mGear imports
    import mgear
    version = "{}.{}.{}".format(mgear.major, mgear.minor, mgear.micro)
    assert mgear.version == version
