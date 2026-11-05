"""API package with a lazy application export for independent CLI tools."""
__all__ = ["app"]


def __getattr__(name):
    if name == "app":
        from .main import app
        globals()[name] = app
        return app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
