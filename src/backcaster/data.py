"""Errors reported when local source data cannot be loaded or resolved."""


class DataLoadError(RuntimeError):
    """Local source files are missing, unreadable, or invalid."""


class PlayerLookupError(RuntimeError):
    pass
