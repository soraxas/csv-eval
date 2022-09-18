import argparse
import logging
import sys

import argcomplete
import pyp

from csv_eval._impl import preprocess_full_statements, Transpiler
from csv_eval._version import __version__

LOGGER = logging.getLogger(__file__)

parser = argparse.ArgumentParser()
parser.add_argument("statements", type=str, help="Python eval statements", nargs="?")
parser.add_argument("-s", "--select", type=str)
parser.add_argument("-n", "--no-header", dest="has_header", action="store_false")
parser.add_argument("-e", "--explain", action="store_true")
parser.add_argument(
    "--no-auto-quote-str-indexer", dest="auto_quote_str_indexer", action="store_false"
)
parser.add_argument("--version", action="version", version=f"csv-eval {__version__}")
parser.add_argument("--debug", action="store_true")

parser.add_argument(
    "-f",
    "--filter",
    help="Filtering based on line",
    type=str,
)


def run():
    # argcomplete.autocomplete(parser)
    _args = parser.parse_args()
    if sys.stdin.isatty():
        parser.print_usage()
        print(f"{parser.prog}: there was no stdin for input.")
        exit(1)

    if _args.debug:
        LOGGER.setLevel(logging.DEBUG)

        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        LOGGER.addHandler(handler)

    LOGGER.debug("Input statement was %s", _args.statements)

    transpiler = Transpiler(
        select_field=_args.select,
        has_header=_args.has_header,
        use_auto_quote=_args.auto_quote_str_indexer,
        filter_str=_args.filter,
    )

    processed_statements, new_cols_headers = preprocess_full_statements(
        _args.statements, _args.auto_quote_str_indexer
    )
    transpiler.add_extra_headers(new_cols_headers)
    full_transpiled_code = transpiler.transpile(processed_statements)

    LOGGER.debug("Transpiled %s", full_transpiled_code)

    pyp_args = transpiler.get_pyp_args()
    pyp_args.append(full_transpiled_code)

    if _args.explain:
        pyp_args.append("--explain")

    pyp.run_pyp(pyp.parse_options(pyp_args))


if __name__ == "__main__":
    run()
