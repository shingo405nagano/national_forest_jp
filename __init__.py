try:
    from .geomesh import *
except ImportError:
    # When running pytest from project root, allow import to fail
    pass

__version__ = "0.1.0"

__all__ = ["geomesh"]
