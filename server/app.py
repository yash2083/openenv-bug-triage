"""Root-level server wrapper for OpenEnv validation."""

from bugtriage_env.server.app import app as app
from bugtriage_env.server.app import main as _package_main


def main() -> None:
    """Delegate to the package server entry point."""
    _package_main()


if __name__ == "__main__":
    main()