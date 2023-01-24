import pytest

from f2ap import markdown


def test_find_hashtags():
    assert markdown.find_hashtags("Hello World! #test #pytest #python #hello") == [
        "test",
        "pytest",
        "python",
        "hello",
    ]


@pytest.mark.parametrize(
    [
        "expected_return",
        "text",
        "one_paragraph",
        "nl2br",
        "autolink",
        "parse_fediverse_tags",
    ],
    [
        (
            '<p>Hello\n<a href="https://en.wikipedia.org/wiki/World">World</a>!</p>',
            "Hello\n[World](https://en.wikipedia.org/wiki/World)!",
            False,
            False,
            False,
            False,
        ),
        (
            'Hello\n<a href="https://en.wikipedia.org/wiki/World">World</a>!',
            "Hello\n[World](https://en.wikipedia.org/wiki/World)!",
            True,
            False,
            False,
            False,
        ),
        (
            '<p>Hello<br />\n<a href="https://en.wikipedia.org/wiki/World">World</a>!</p>',
            "Hello\n[World](https://en.wikipedia.org/wiki/World)!",
            False,
            True,
            False,
            False,
        ),
        (
            '<p>Hello\nWorld: <a href="https://en.wikipedia.org/wiki/World!" rel="nofollow">https://en.wikipedia.org/wiki/World!</a></p>',
            "Hello\nWorld: https://en.wikipedia.org/wiki/World!",
            False,
            False,
            True,
            False,
        ),
        (
            '<p>Hello\n<a href="https://solarsystem.org/@Earth">@Earth@solarsystem.org</a>!</p>',
            "Hello\n@Earth@solarsystem.org!",
            False,
            False,
            False,
            True,
        ),
    ],
)
def test_parse_markdown(
    expected_return: str,
    text: str,
    one_paragraph: bool,
    nl2br: bool,
    autolink: bool,
    parse_fediverse_tags: bool,
):
    assert (
        markdown.parse_markdown(
            text, one_paragraph, nl2br, autolink, parse_fediverse_tags
        )
        == expected_return
    )
