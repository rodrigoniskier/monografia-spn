#!/usr/bin/env python
"""Django command-line utility for Monografia SPN."""
import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "monografiaspn.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Django não está disponível. Ative o ambiente virtual e instale requirements.txt."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()

