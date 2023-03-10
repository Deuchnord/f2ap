from typing import Optional
from uuid import UUID

from pydantic import BaseModel
from datetime import datetime

from .markdown import parse_markdown
from .config import Actor as ConfigActor, Configuration

W3C_ACTIVITYSTREAMS_PUBLIC = "https://www.w3.org/ns/activitystreams#Public"


class Markdown(str):
    def __init__(
        self,
        txt: str,
        one_paragraph: bool = False,
        nl2br: bool = True,
        autolink: bool = True,
        parse_fediverse_tags: bool = True,
    ):
        self.txt = txt
        self.one_paragraph = one_paragraph
        self.nl2br = nl2br
        self.autolink = autolink
        self.parse_fediverse_tags = parse_fediverse_tags

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, value):
        if not isinstance(value, str):
            raise TypeError("must be a string")

        return cls(value)

    def __str__(self) -> str:
        return parse_markdown(
            self.txt,
            one_paragraph=self.one_paragraph,
            nl2br=self.nl2br,
            autolink=self.autolink,
            parse_fediverse_tags=self.parse_fediverse_tags,
        )


def activitystream(contexts: list[str] = None, hide_properties: list[str] = None):
    if contexts is None:
        contexts = []

    if hide_properties is None:
        hide_properties = []

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
            d = {"@context": ["https://www.w3.org/ns/activitystreams"] + contexts}

            for key, value in self.old_dict(
                include=include,
                exclude=exclude,
                by_alias=by_alias,
                skip_defaults=skip_defaults,
                exclude_unset=exclude_unset,
                exclude_defaults=exclude_defaults,
                exclude_none=exclude_none,
            ).items():
                if key in hide_properties:
                    continue

                d[key] = value

            return d

        cls.dict = new_dict
        return cls

    return decorator


class Attachment(BaseModel):
    type: str


class PropertyValue(Attachment):
    name: str
    value: str

    @classmethod
    def make(cls, name: str, value: str):
        return cls(type="PropertyValue", name=name, value=value)


class Link(Attachment):
    href: str

    @classmethod
    def make(cls, href: str):
        return cls(type="Link", href=href)


class File(Attachment):
    mediaType: Optional[str]
    url: str

    @classmethod
    def make(cls, url: str, mime_type: str):
        return cls(type="Image", mediaType=mime_type, url=url)


class PublicKey(BaseModel):
    id: str
    owner: str
    publicKeyPem: str


@activitystream(contexts=["https://w3id.org/security/v1"])
class Actor(BaseModel):
    id: str
    url: str
    type: str = "Person"
    preferredUsername: str
    name: str
    summary: Markdown
    icon: File
    image: File
    attachment: list[PropertyValue]
    following: str
    followers: str
    inbox: str
    outbox: str
    publicKey: PublicKey

    @classmethod
    def make_attachments(cls, attachments: {str: str}) -> list[Attachment]:
        l = []
        for key, value in attachments.items():
            l.append(PropertyValue.make(key, Markdown(value)))

        return l

    @classmethod
    def make(cls, actor: ConfigActor):
        return cls(
            id=actor.id,
            url=actor.config.website.url,
            preferredUsername=actor.preferred_username,
            name=actor.display_name,
            summary=Markdown(actor.summary),
            icon=File.make(actor.avatar, f"{actor.id}/avatar"),
            image=File.make(actor.header, f"{actor.id}/header"),
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


@activitystream(hide_properties=["uuid"])
class Note(BaseModel):
    uuid: UUID
    id: str
    name: Optional[str]
    type: str = "Note"
    mediaType: str = "text/html"
    inReplyTo: Optional[str]
    published: datetime
    url: str
    attributedTo: str
    to: list[str] = [W3C_ACTIVITYSTREAMS_PUBLIC]
    cc: list[str] = []
    content: Markdown
    attachment: list[Attachment] = []
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
    first: Optional[str]
    last: Optional[str]
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
                prev=f"{endpoint}?page={previous_page}"
                if previous_page is not None
                else None,
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
