from typing import Optional, Union


class HttpError(IOError):
    def __init__(self, status_code: int, body: Optional[Union[str, dict]]):
        self.status_code = status_code
        self.body = body


class UnauthorizedHttpError(HttpError):
    def __init__(self, body: Optional[Union[str, dict]]):
        super().__init__(401, body)
