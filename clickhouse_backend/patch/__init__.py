from .fields import *
from .fields import __all__ as fields_all
from .functions import *
from .functions import __all__ as functions_all
from .migrations import *
from .migrations import __all__ as migrations_all

__all__ = [
    "patch_all",
    *fields_all,
    *functions_all,
    *migrations_all,
]


def patch_all():
    patch_functions()
    patch_fields()
    patch_migrations()
