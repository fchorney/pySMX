import argparse
from typing import Optional, Sequence

from loguru import logger


def main(args: Optional[Sequence[str]] = None):
    pargs = parse_args(args=args)
    logger.info(f"Parsed Args: {pargs}")


def parse_args(args: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="StepManiaX SDK for Python")

    return parser.parse_args(args)


if __name__ == "__main__":
    main()
