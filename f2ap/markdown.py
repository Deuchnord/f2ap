import re

from markdown import markdown as _markdown
from markdown.preprocessors import Preprocessor
from markdown.extensions import Extension

EXT_NL2BR = "markdown.extensions.nl2br"
EXT_LINKIFY = "mdx_linkify"


def find_hashtags(s: str) -> [str]:
    pattern = re.compile("#([^0-9-][^. -]*)")
    for tag in pattern.findall(s):
        yield tag


class FediverseTagsParser(Preprocessor):
    def run(self, lines: list[str]) -> list[str]:
        pattern = re.compile("@(?P<username>[a-zA-Z0-9_]+)@(?P<domain>[a-z0-9_.-]+)")
        _lines = []

        for line in lines:
            for username, domain in pattern.findall(line):
                actor_id = f"https://{domain}/@{username}"
                line = line.replace(f"@{username}@{domain}", f"[@{username}@{domain}]({actor_id})")

            _lines.append(line)

        return _lines


class FediverseExtension(Extension):
    def extendMarkdown(self, md):
        md.preprocessors.register(FediverseTagsParser(md), "fediverse_tags_parser", 0)


def parse_markdown(
    text: str,
    one_paragraph: bool = False,
    nl2br: bool = True,
    autolink: bool = True,
    parse_fediverse_tags: bool = True,
) -> str:
    extensions = []

    if nl2br:
        extensions.append(EXT_NL2BR)
    if autolink:
        extensions.append(EXT_LINKIFY)
    if parse_fediverse_tags:
        extensions.append(FediverseExtension())

    # Replace the "#" characters with &num; to prevent the markdown package to parse it as a title.
    # See https://github.com/Python-Markdown/markdown/blob/383de86c64101b8d14768d9a247c9efc97d703bd/tests/test_syntax/blocks/test_headers.py#L202-L207
    md = _markdown(text.replace('#', '&num;').replace("&&num;", "&#"), extensions=extensions)

    if one_paragraph:
        md = md.removeprefix("<p>").removesuffix("</p>")

    return md
