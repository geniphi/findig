#coding: utf-8
import pytest
from findig.tools.protector.scopeutil import *


@pytest.mark.parametrize("scopes,expected", [
    (
        ["user+urc", "foo", "user+d", "bar+d"],
        ["user+c", "user+r", "user+u", "foo+r", "user+d", "bar+d"]
    ),
    (
        # Unicode scope names
        ["κόσμε+urc", "Zwölf", "κόσμε+d", "jordbær+d"],
        ["κόσμε+c", "κόσμε+r", "κόσμε+u", "Zwölf+r", "κόσμε+d", "jordbær+d"]
    ),
    (
        # invalid scope permissions are omitted
        ["foo+h", "foo+c"],
        ValueError("foo+h")
    ),
    (
        # Badly formed scopes raise an error
        ["foo+"],
        ValueError("foo+")
    )
])
def test_normalize(scopes, expected):
    if isinstance(expected, Exception):
        with pytest.raises(type(expected)):
            normalized = normalize_scope_items(scopes)
            assert sorted(normalized) == sorted(expected)
    else:
        normalized = normalize_scope_items(scopes)
        assert sorted(normalized) == sorted(expected)

def test_normalize_multiple():
    scopes = ["user+urc", "foo", "user+d", "bar+d"]
    for i in range(100):
        scopes = normalize_scope_items(scopes)
    
    assert sorted(scopes) == sorted(["user+c", "user+r", "user+u", "foo+r", "user+d", "bar+d"])

@pytest.mark.parametrize("root,child,expected", [
    ("user+crud", "user/emails+u", True),
    ("jordbær+ud", "jordbær/sub+d", True),
    ("user+crud", "user+u", True),
    ("Zwölf+r", "Zwolf+r", False),
    ("user/emails+u", "user+u", False),
    ("user+cru", "user+d", False),
    ("κόσμε+r", "κόσμε+u", False),
])
def test_sub_scopes(root, child, expected):
    assert check_encapsulates(root, child) == expected
