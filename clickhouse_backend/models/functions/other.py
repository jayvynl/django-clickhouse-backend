from .base import Func

__all__ = [
    "currentDatabase",
    "hostName",
]


class currentDatabase(Func):
    arity = 0


class hostName(Func):
    arity = 0
