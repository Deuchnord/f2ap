import mimetypes
from typing import Optional

from pydantic import BaseModel
from datetime import datetime

from .markdown import parse_markdown
from .config import Actor as ConfigActor, Configuration

W3C_ACTIVITYSTREAMS_PUBLIC = "https://www.w3.org/ns/activitystreams#Public"


class Markdown:
    def __init__(
        self,
        txt: str,
        one_paragraph: bool = False,
        nl2br: bool = True,
        autolink: bool = True,
        parse_fediverse_tags: bool = True,
    ):
        if not isinstance(txt, str):
            raise TypeError("must be a string")

        self.txt = txt
        self.one_paragraph = one_paragraph
        self.nl2br = nl2br
        self.autolink = autolink
        self.parse_fediverse_tags = parse_fediverse_tags

    def __str__(self) -> str:
        return parse_markdown(
            self.txt,
            one_paragraph=self.one_paragraph,
            nl2br=self.nl2br,
            autolink=self.autolink,
            parse_fediverse_tags=self.parse_fediverse_tags,
        )


def activitystream(*additional_contexts: str):
    def decorator(cls: type):
        if not issubclass(cls, BaseModel):
            raise TypeError(
                "Class %s must be a subclass of %s."
                % (cls.__name__, BaseModel.__name__)
            )

        cls.old_dict = cls.dict

        def new_dict(
            self,
            *,
            include=None,
            exclude=None,
            by_alias=False,
            skip_defaults=None,
            exclude_unset=False,
            exclude_defaults=False,
            exclude_none=False,
        ):
            d = {
                "@context": ["https://www.w3.org/ns/activitystreams"]
                + list(additional_contexts)
            }
            for key, value in self.old_dict(
                include=include,
                exclude=exclude,
                by_alias=by_alias,
                skip_defaults=skip_defaults,
                exclude_unset=exclude_unset,
                exclude_defaults=exclude_defaults,
                exclude_none=exclude_none,
            ).items():
                d[key] = value

            return d

        cls.dict = new_dict
        return cls

    return decorator


class File(BaseModel):
    type: str
    mediaType: str
    url: str


class ImageFile(File):
    @classmethod
    def from_file(cls, path: str, url: str):
        file_type, _ = mimetypes.guess_type(path, strict=True)
        if file_type.split("/")[0] != "image":
            raise TypeError(
                f'Invalid file type for file "{path}". Check it is a valid image.'
            )

        return cls(type="Image", mediaType=file_type, url=url)


class Attachment(BaseModel):
    type: str
    name: str
    value: str


class PropertyValueAttachment(Attachment):
    def __init__(self, name: str, value: str):
        super().__init__(type="PropertyValue", name=name, value=value)


class PublicKey(BaseModel):
    id: str
    owner: str
    publicKeyPem: str


@activitystream("https://w3id.org/security/v1")
class Actor(BaseModel):
    id: str
    url: str
    type: str = "Person"
    preferredUsername: str
    name: str
    summary: str
    icon: Optional[File]
    image: Optional[File]
    attachment: list[PropertyValueAttachment]
    following: str
    followers: str
    inbox: str
    outbox: str
    publicKey: PublicKey

    @classmethod
    def make_attachments(cls, attachments: {str: str}) -> list[Attachment]:
        l = []
        for key, value in attachments.items():
            l.append(PropertyValueAttachment(key, str(Markdown(value))))

        return l

    @classmethod
    def make(cls, actor: ConfigActor):
        return cls(
            id=actor.id,
            url=actor.config.website.url,
            preferredUsername=actor.preferred_username,
            name=actor.display_name,
            summary=str(Markdown(actor.summary)),
            icon=(
                ImageFile.from_file(actor.avatar, f"{actor.id}/avatar")
                if actor.avatar is not None
                else None
            ),
            image=(
                ImageFile.from_file(actor.header, f"{actor.id}/header")
                if actor.header is not None
                else None
            ),
            attachment=cls.make_attachments(actor.attachments),
            following=f"{actor.id}/following",
            followers=f"{actor.id}/followers",
            inbox=f"{actor.id}/inbox",
            outbox=f"{actor.id}/outbox",
            publicKey=PublicKey(
                id=f"{actor.key_id}",
                owner=actor.id,
                publicKeyPem=actor.public_key,
            ),
        )


@activitystream()
class Note(BaseModel):
    id: str
    type: str = "Note"
    inReplyTo: Optional[str] = None
    published: datetime
    url: str
    attributedTo: str
    to: list[str] = [W3C_ACTIVITYSTREAMS_PUBLIC]
    cc: list[str] = []
    content: str
    attachment: list[File] = []
    tag: list[str] = []


@activitystream()
class Message(BaseModel):
    id: str
    type: str = "Create"
    actor: str
    published: datetime
    to: list[str] = [W3C_ACTIVITYSTREAMS_PUBLIC]
    cc: list[str] = []
    object: Note


@activitystream()
class OrderedCollection(BaseModel):
    type: str = "OrderedCollection"
    totalItems: int
    first: Optional[str] = None
    last: Optional[str] = None
    prev: Optional[str] = None
    next: Optional[str] = None
    orderedItems: Optional[list] = None

    @classmethod
    def make(
        cls, endpoint: str, items: [str], page: int = None, items_per_page: int = 10
    ):
        first_page = 1
        last_page = int(len(items) / items_per_page) + (
            1 if len(items) % items_per_page > 0 else 0
        )

        if page is None:
            page = 0

        if page > 0:
            collection_type = "OrderedCollectionPage"
            first = (page - 1) * items_per_page
            last = first + items_per_page
            ordered_items = items[first:last]

            if len(ordered_items) == 0:
                return None

            next_page = (page + 1) if page < last_page else None
            previous_page = page - 1 if page > 1 else None

            return cls(
                type=collection_type,
                totalItems=len(items),
                first=f"{endpoint}?page={first_page}",
                last=f"{endpoint}?page={last_page}",
                prev=(
                    f"{endpoint}?page={previous_page}"
                    if previous_page is not None
                    else None
                ),
                next=f"{endpoint}?page={next_page}" if next_page is not None else None,
                orderedItems=ordered_items,
            )

        if len(items) > 0:
            return cls(
                totalItems=len(items),
                first=f"{endpoint}?page={first_page}",
                last=f"{endpoint}?page={last_page}",
            )

        return cls(totalItems=0)


class Tag(BaseModel):
    type: str = "Hashtag"
    href: str
    name: str

    @classmethod
    def make(cls, config: Configuration, name: str):
        return cls(name=f"#{name}", href=f"https://{config.url}/tags/{name}")
