"""Dispatch the four assignment commands."""
import argparse
import importlib
import sys

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['extract', 'build', 'search', 'test'])
    args, rest = p.parse_known_args()
    sys.argv = [sys.argv[0]] + rest
    importlib.import_module({'extract': 'extract_articles', 'build': 'build_index', 'search': 'search', 'test': 'generate_tests'}[args.command]).main()

if __name__ == '__main__':
    main()
