"""txtfmt — AI-powered text formatting for your terminal."""

try:
    from txtfmt._version import __version__
except ImportError:
    # package not installed (e.g. running directly from source without a build step)
    __version__ = "0.0.0.dev0"
