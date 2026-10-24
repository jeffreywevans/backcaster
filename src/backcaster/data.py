"""Errors reported when local source data cannot be loaded or resolved."""


class DataFetchError(RuntimeError):
    pass


class PlayerLookupError(RuntimeError):
    pass
