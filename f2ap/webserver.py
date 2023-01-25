import logging
import threading

import uvicorn
import json
import base64
import hashlib

from uuid import UUID
from typing import Union, Any, Optional
from fastapi import FastAPI, BackgroundTasks
from fastapi import Request
from fastapi.responses import Response, JSONResponse
from pydantic import BaseModel

from . import postie, activitypub
from .config import Configuration
from .data import Database
from .exceptions import HttpError
from .model import OrderedCollection, Actor
from .json import ActivityJsonEncoder

W3C_ACTIVITY_STREAM = "https://www.w3.org/ns/activitystreams"


class FollowThread(threading.Thread):
    def __init__(self, config: Configuration, users: [str]):
        super().__init__()
        self.config = config
        self.users = users

    def run(self) -> None:
        activitypub.follow_users(self.config, self.users)


class ActivityJSONResponse(JSONResponse):
    """A special version of JSONResponse, with the good media type."""

    def __init__(
        self,
        content: Any = None,
        status_code: int = 200,
        headers: {str: str} = None,
        background: BackgroundTasks = None,
    ):
        super().__init__(
            content, status_code, headers, "application/activity+json", background
        )

    def render(self, content: Any) -> bytes:
        return json.dumps(
            content,
            cls=ActivityJsonEncoder,
            ensure_ascii=False,
            allow_nan=False,
            indent=None,
            separators=(",", ":"),
        ).encode("utf-8")


def respond(o: BaseModel, status_if_none: int = 404) -> Union[BaseModel, Response]:
    if o is None:
        return Response(status_code=status_if_none)

    return o


def get_activitypub_decorator(self: FastAPI):
    def decorator(
        path: str,
        responds_with: Any = None,
        method: str = "get",
        ignore_unset: bool = False,
        status_code: int = 200,
    ):
        def f(coroutine):
            return self.add_api_route(
                path,
                status_code=status_code,
                endpoint=coroutine,
                methods=[method],
                response_class=ActivityJSONResponse,
                response_model_exclude_unset=ignore_unset,
                response_model=responds_with,
            )

        return f

    return decorator


def get_server(config: Configuration, skip_following: bool = False):
    app = FastAPI(docs_url=None)
    app.activitypub = get_activitypub_decorator(app)
    db = Database(config)
    get_server.following = None

    if skip_following:
        get_server.following = []
        logging.debug("Following is disabled.")

    @app.middleware("http")
    async def on_request(request: Request, call_next):
        logging.debug(
            f"{request.method} {request.url} with headers: {dict(request.headers)}"
        )

        # If the server has just started, follow the users specified in the configuration.
        if not skip_following and get_server.following is None:
            get_server.following = []
            follow_task = FollowThread(config, config.actor.following)
            follow_task.start()

        # Check if user has asked for a known URL (e.g. the URL of a blog post)
        request_url = str(request.url)
        if request_url.startswith("http://"):
            request_url = request_url.replace("http://", "https://", 1)

        logging.debug(f"Searching {request_url} in the notes")
        note = db.get_note(url=request_url)
        if note is not None:
            logging.debug("Note found!")
            return ActivityJSONResponse(note.dict())

        return await call_next(request)

    @app.on_event("shutdown")
    async def on_stop():
        if get_server.following is not None:
            activitypub.unfollow_users(config, get_server.following)

    @app.get("/.well-known/webfinger")
    async def webfinger(resource: Union[str, None]):
        subject = f"acct:{config.actor.preferred_username}@{config.url}"
        if resource is None or resource != subject:
            return Response(status_code=404)

        return JSONResponse(
            media_type="application/jrd+json",
            content={
                "subject": subject,
                "links": [
                    {
                        "rel": "self",
                        "type": "application/activity+json",
                        "href": config.actor.id,
                    }
                ],
            },
        )

    @app.activitypub("/actors/{username}")
    async def get_actor(username: str):
        if username != config.actor.preferred_username:
            return Response(status_code=404)

        return respond(Actor.make(config.actor))

    @app.activitypub(
        "/actors/{username}/following",
        ignore_unset=True,
        responds_with=OrderedCollection,
    )
    async def get_following(username, page: Optional[int] = 0):
        if username != config.actor.preferred_username:
            return Response(status_code=404)

        following = []
        for _, account in get_server.following:
            following.append(account)

        return respond(
            OrderedCollection.make(f"{config.actor.id}/following", following, page)
        )

    @app.activitypub(
        "/actors/{username}/followers",
        ignore_unset=True,
        responds_with=OrderedCollection,
    )
    async def get_followers(username: str, page: Optional[int] = 0):
        if username != config.actor.preferred_username:
            return Response(status_code=404)

        return respond(
            OrderedCollection.make(
                f"{config.actor.id}/followers", db.get_followers(), page
            )
        )

    @app.activitypub(
        "/actors/{username}/outbox", ignore_unset=True, responds_with=OrderedCollection
    )
    async def get_outbox(username: str, page: Optional[int] = None):
        if username != config.actor.preferred_username:
            return Response(status_code=404)

        return respond(
            OrderedCollection.make(f"{config.actor.id}/outbox", db.get_messages(), page)
        )

    @app.activitypub("/actors/{username}/inbox", method="POST", status_code=202)
    async def post_inbox(
        username: str, request: Request, background_tasks: BackgroundTasks
    ) -> Union[None, Response]:
        if username != config.actor.preferred_username:
            return Response(status_code=404)

        body = await request.body()

        expected_digest = request.headers.get("digest")
        actual_digest = (
            f"SHA-256={base64.b64encode(hashlib.sha256(body).digest()).decode()}"
        )
        if actual_digest != expected_digest:
            logging.debug(f"Expected digest from header: {expected_digest}")
            logging.debug(f"Actual computed digest: {actual_digest}")
            return Response("Invalid digest", status_code=401)

        inbox = await request.json()

        try:
            response = activitypub.handle_inbox(
                config,
                db,
                dict(request.headers),
                inbox,
                lambda i, a: get_server.following.append((i, a)),
            )
        except HttpError as e:
            return Response(e.body, status_code=e.status_code)

        if response is None:
            return

        actor, activity_response = response

        if activity_response is not None:
            activity_response["@context"] = W3C_ACTIVITY_STREAM
            background_tasks.add_task(postie.deliver, config, actor, activity_response)

    @app.activitypub("/messages/{uuid}")
    async def get_messages(uuid: UUID):
        return respond(db.get_message(uuid))

    return app


def start_server(
    config: Configuration, port: int, log_level: str, skip_following: bool = False
):
    uvicorn.run(
        get_server(config, skip_following),
        host="0.0.0.0",
        port=port,
        log_level=log_level.lower(),
        headers=[("server", "f2ap")],
    )
