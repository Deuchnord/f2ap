from bs4 import BeautifulSoup, Comment

DEFAULT_AUTHORIZED_TAGS = ["a", "p", "br"]


# Inspired from https://gist.github.com/braveulysses/120193
def sanitize(document: str, keep: [str] = None) -> str:
    if keep is None:
        keep = DEFAULT_AUTHORIZED_TAGS

    soup = BeautifulSoup(document, features="html.parser")

    # Remove HTML comments
    for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
        comment.extract()

    # Remove unauthorized tags
    for tag in soup.find_all():
        if tag.name.lower() in keep:
            continue

        tag.unwrap()

    return str(soup)
