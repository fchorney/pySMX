import argparse
from collections.abc import Sequence

from loguru import logger


def main(args: Sequence[str] | None = None):
    pargs = parse_args(args=args)
    logger.info(f"Parsed Args: {pargs}")


def parse_args(args: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="StepManiaX SDK for Python")

    return parser.parse_args(args)


if __name__ == "__main__":
    main()
