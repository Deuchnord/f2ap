# Note: this file purposely has an extra underscore in its name.
# This is a fix to this issue:
# https://stackoverflow.com/questions/27372347/beautifulsoup-importerror-no-module-named-html-entities

from f2ap import html


def test_sanitize_with_default_authorized_tags():
    original = '<p><strong>Hello</strong> <a href="https://en.wikipedia.org/wiki/World">World</a>!</p>'
    expected = '<p>Hello <a href="https://en.wikipedia.org/wiki/World">World</a>!</p>'

    assert expected == html.sanitize(original)


def test_sanitize_with_custom_tags():
    original = '<p><strong>Hello</strong> <a href="https://en.wikipedia.org/wiki/World">World</a>!</p>'
    expected = "<strong>Hello</strong> World!"

    assert expected == html.sanitize(original, keep=["strong"])


def test_sanitize_with_no_custom_tags():
    original = '<p><strong>Hello</strong> <a href="https://en.wikipedia.org/wiki/World">World</a>!</p>'
    expected = "Hello World!"

    assert expected == html.sanitize(original, keep=[])


def test_sanitize_removes_comments():
    original = (
        '<p><!-- Hello --> <a href="https://en.wikipedia.org/wiki/World">World</a>!</p>'
    )
    expected = '<p> <a href="https://en.wikipedia.org/wiki/World">World</a>!</p>'

    assert expected == html.sanitize(original)
