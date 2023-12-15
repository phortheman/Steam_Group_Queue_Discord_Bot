import re
import pytest


@pytest.fixture
def regex_pattern() -> re.Pattern:
    return re.compile(r"(https?:\/\/store\.steampowered\.com\/app\S+)")


def test_no_matches(regex_pattern: re.Pattern):
    message = r"!add this is some bogus command input"
    matches = regex_pattern.findall(message)
    assert len(matches) == 0


def test_root_path_not_match(regex_pattern: re.Pattern):
    message = r"!add https://store.steampowered.com/"
    matches = regex_pattern.findall(message)
    assert len(matches) == 0


def test_single_match(regex_pattern: re.Pattern):
    message = r"!add https://store.steampowered.com/app/22330/The_Elder_Scrolls_IV_Oblivion_Game_of_the_Year_Edition/"
    matches = regex_pattern.findall(message)
    assert len(matches) == 1
    assert (
        matches.pop()
        == r"https://store.steampowered.com/app/22330/The_Elder_Scrolls_IV_Oblivion_Game_of_the_Year_Edition/"
    )


def test_multiple_matches(regex_pattern: re.Pattern):
    message = (
        r"!add "
        r"https://store.steampowered.com/app/22330/The_Elder_Scrolls_IV_Oblivion_Game_of_the_Year_Edition/ "
        r"https://store.steampowered.com/app/22370/Fallout_3_Game_of_the_Year_Edition/"
    )
    matches = regex_pattern.findall(message)
    assert len(matches) == 2


def test_app_id_valid(regex_pattern: re.Pattern):
    message = r"!add https://store.steampowered.com/app/22370"
    matches = regex_pattern.findall(message)
    assert len(matches) == 1


def test_dirty_url(regex_pattern: re.Pattern):
    message = r"!add https://store.steampowered.com/app/22370/Fallout_3_Game_of_the_Year_Edition/%20has%20other%20stuff"
    matches = regex_pattern.findall(message)
    assert len(matches) == 1


def test_dirty_command(regex_pattern: re.Pattern):
    message = r"!add https://store.steampowered.com/app/22370/Fallout_3_Game_of_the_Year_Edition/  oops there are some extra spaces and a lot of character afterwards"
    matches = regex_pattern.findall(message)
    assert len(matches) == 1
    assert (
        matches.pop()
        == r"https://store.steampowered.com/app/22370/Fallout_3_Game_of_the_Year_Edition/"
    )
