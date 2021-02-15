import sys

from plbmng import engine


def main():
    e = engine.Engine()
    e.init_interface()


if __name__ == "__main__":
    sys.exit(main())
