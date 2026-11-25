"""Specification tests for engine/mime/parse.py.

The suite starts red on purpose: all 15 tests fail with NotImplementedError
until the eight stubs are implemented.
"""

import pytest

from engine.mime.parse import (
    default_charset,
    mime_batch,
    parse_continutation,
    parse_params,
    split_type,
    tokenize_params,
    unquote_value,
    validate,
)


def test_main_type_is_lowercased():
    assert split_type("  Text/HTML ; charset=UTF-8") == "text/html"


def test_parameter_names_are_lowercased():
    tokens = ['Charset="utf-8"', "BOUNDARY=abc"]
    assert parse_params(tokens) == {"charset": "utf-8", "boundary": "abc"}


def test_semicolon_inside_quotes_is_not_split():
    text = 'text/plain; boundary="a;b"; charset=utf-8'
    assert tokenize_params(text) == ['boundary="a;b"', "charset=utf-8"]


def test_backslash_escaped_quote_is_decoded():
    assert unquote_value(r'"a\"b"') == 'a"b'
    assert unquote_value(r'"a\\b"') == "a\\b"


def test_unclosed_quote_is_reported():
    assert validate('text/plain; charset="utf-8') == ["unclosed quote"]
    with pytest.raises(ValueError):
        unquote_value('"utf-8')


def test_duplicate_parameter_keeps_first():
    assert parse_params(["boundary=first", "boundary=second"]) == {
        "boundary": "first"
    }


def test_empty_parameter_value_is_kept():
    assert parse_params(["charset=", "boundary=xyz"]) == {
        "charset": "",
        "boundary": "xyz",
    }


def test_continuation_segments_are_joined_and_gaps_rejected():
    assert parse_continutation(["subject*1=World", "subject*0=Hello"]) == {
        "subject": "HelloWorld"
    }
    with pytest.raises(ValueError):
        parse_continutation(["subject*0=Hello", "subject*2=!"])


def test_default_charset_depends_on_media_type():
    policy = {"text/plain": "utf-8", "application/octet-stream": "us-ascii"}
    assert default_charset("text/plain", policy) == "utf-8"
    assert default_charset("application/octet-stream", policy) == "us-ascii"
    with pytest.raises(ValueError):
        default_charset("image/png", policy)


def test_batch_does_not_reuse_parameters_between_items():
    policy = {"text/plain": "utf-8", "text/html": "utf-8"}
    texts = ["text/plain; charset=utf-8", "text/html; boundary=abc"]
    result = mime_batch(texts, policy)
    assert result[texts[0]]["params"] == {"charset": "utf-8"}
    assert result[texts[1]]["params"] == {"boundary": "abc"}


def test_standard_type_without_parameters():
    text = "text/plain"
    assert split_type(text) == "text/plain"
    assert tokenize_params(text) == []
    assert parse_params(tokenize_params(text)) == {}
    assert validate(text) == []


def test_quoted_parameter_value_is_parsed():
    text = 'text/plain; charset="utf-8"'
    assert parse_params(tokenize_params(text)) == {"charset": "utf-8"}


def test_quoted_semicolon_is_preserved_in_parsed_value():
    text = 'text/plain; note="a; b"; boundary=xyz'
    assert parse_params(tokenize_params(text)) == {
        "note": "a; b",
        "boundary": "xyz",
    }


def test_duplicate_parameters_keep_first_in_full_parse():
    text = "text/plain; charset=utf-8; Charset=us-ascii"
    assert parse_params(tokenize_params(text)) == {"charset": "utf-8"}


def test_batch_matches_individual_parses():
    policy = {"text/plain": "utf-8", "application/json": "utf-8"}
    texts = [
        "text/plain; charset=utf-8",
        "application/json; profile=strict",
    ]
    expected = {
        texts[0]: {
            "media_type": "text/plain",
            "params": {"charset": "utf-8"},
            "charset": "utf-8",
        },
        texts[1]: {
            "media_type": "application/json",
            "params": {"profile": "strict"},
            "charset": "utf-8",
        },
    }
    batch = mime_batch(texts, policy)
    assert batch == expected
    assert mime_batch([texts[0]], policy)[texts[0]] == expected[texts[0]]
    assert mime_batch([texts[1]], policy)[texts[1]] == expected[texts[1]]