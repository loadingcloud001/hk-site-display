from app.priority import classify


def test_t8_outranks_amber_hsww():
    got = classify(["TC8NE"], "amber")
    assert got["band"] == "P0"


def test_amber_hsww_is_p3_when_only_tc1():
    got = classify(["TC1"], "amber")
    assert got["band"] == "P3"


def test_no_warning_is_p4():
    assert classify([], "none")["band"] == "P4"


def test_black_rain_is_p0():
    assert classify(["WRAINB"], "none")["band"] == "P0"


def test_pre8_is_p1():
    assert classify(["WTCPRE8"], "none")["band"] == "P1"


def test_red_hsww_is_p2():
    assert classify([], "red")["band"] == "P2"


def test_extreme_conditions_are_p0_whatever_hko_has_issued():
    for codes, level in (([], "none"), (["TC10"], "none"), (["WRAINB", "TC8NE"], "black"), (["TC1"], "amber")):
        assert classify(codes, level, extreme=True) == {"band": "P0", "headlineZh": "「極端情況」"}


def test_without_extreme_conditions_the_bands_are_unchanged():
    assert classify(["TC8NE"], "amber", extreme=False)["band"] == "P0"
    assert classify([], "none", extreme=False)["band"] == "P4"
