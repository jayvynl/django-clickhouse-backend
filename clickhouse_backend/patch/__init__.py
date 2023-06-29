from .fields import patch_jsonfield
from .functions import patch_functions


def patch_all():
    patch_jsonfield()
    patch_functions()
