import sys

from plbmng import engine


def main():
    """Start the engine and initialize the plbmng interface."""
    e = engine.Engine()
    e.init_interface()


if __name__ == "__main__":
    sys.exit(main())
