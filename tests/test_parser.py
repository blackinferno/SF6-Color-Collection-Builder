from app.parser import parse_color_filename


def test_parse_normal_color_file() -> None:
    parsed = parse_color_filename("esf001_001_cmd_002.user.2")

    assert parsed is not None
    assert parsed.character == "esf001"
    assert parsed.costume == "001"
    assert parsed.type == "normal"
    assert parsed.slot == "002"


def test_parse_dx_color_file_case_insensitive() -> None:
    parsed = parse_color_filename("ESF001_001_CMD_DX_003.USER.2")

    assert parsed is not None
    assert parsed.character == "esf001"
    assert parsed.costume == "001"
    assert parsed.type == "dx"
    assert parsed.slot == "003"


def test_parse_ex_color_file() -> None:
    parsed = parse_color_filename("nested/esf001_002_cmd_ex_004.user.2")

    assert parsed is not None
    assert parsed.character == "esf001"
    assert parsed.costume == "002"
    assert parsed.type == "ex"
    assert parsed.slot == "004"


def test_rejects_slot_above_ten() -> None:
    assert parse_color_filename("esf001_001_cmd_011.user.2") is None


def test_rejects_unsupported_filename() -> None:
    assert parse_color_filename("esf001_001_cmd_002.user") is None

