"""MRQlab local execution agent.

``__version__`` is the single source of truth for the agent's
runtime-compatibility version. ``mrqlab_agent.license`` derives its
``RUNTIME_VERSION`` from it, so a signed lease's ``software`` window is checked
against one value that cannot silently drift from the shipped package.
"""

__version__ = "1.0.0"
