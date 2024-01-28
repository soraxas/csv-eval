import argparse
import logging
import sys

import argcomplete
import pyp

from csv_eval._impl import preprocess_full_statements, Transpiler
from csv_eval._version import __version__
from csv_eval.utils import LOGGER

parser = argparse.ArgumentParser()
parser.add_argument("statements", type=str, help="Python eval statements", nargs="?")
parser.add_argument("--transpose", action="store_true")
parser.add_argument("-s", "--select", type=str)
parser.add_argument("-n", "--no-header", dest="has_header", action="store_false")
parser.add_argument("-e", "--explain", action="store_true")
parser.add_argument(
    "--no-auto-quote-raw-str", dest="auto_quote_raw_str", action="store_false"
)
parser.add_argument("--version", action="version", version=f"csv-eval {__version__}")
parser.add_argument("--debug", action="store_true")

parser.add_argument(
    "-f",
    "--filter",
    help="Filtering based on line, before the processing",
    type=str,
)

parser.add_argument(
    "-af",
    "--after-filter",
    help="Filtering based on line, after the processing",
    type=str,
)

parser.add_argument(
    "--skiprows",
    help="Skip the initial row",
    type=int,
    default=0,
)

parser.add_argument(
    "--headers",
    help="Set custom headers",
    nargs="+",
    type=str,
    default=None,
)

parser.add_argument(
    "--pretty",
    help="Pretty print",
    action="store_true",
)


def run():
    argcomplete.autocomplete(parser)
    _args = parser.parse_args()
    if sys.stdin.isatty() and not _args.explain:
        parser.print_usage()
        print(f"{parser.prog}: there was no stdin for input.")
        exit(1)

    for _ in range(_args.skiprows):
        next(sys.stdin)

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

    if _args.transpose:
        pyp_args = [
            "-b",
            "rows=[]",
            "-a",
            'map(lambda x: ",".join(x), zip(*rows))',
            'rows.append(x.split(","))',
        ]

    else:
        transpiler = Transpiler(_args)

        processed_statements, new_cols_headers = preprocess_full_statements(
            _args.statements, _args.auto_quote_raw_str
        )
        transpiler.add_extra_headers(new_cols_headers)
        full_transpiled_code = transpiler.transpile(processed_statements)

        LOGGER.debug("Transpiled %s", full_transpiled_code)

        pyp_args = transpiler.get_pyp_args()
        pyp_args.append(full_transpiled_code)

    if _args.explain:
        pyp_args.append("--explain")

    if _args.pretty and not _args.explain:
        import io
        from contextlib import redirect_stdout

        f = io.StringIO()
        with redirect_stdout(f):
            pyp.run_pyp(pyp.parse_options(pyp_args))
        import pandas as pd

        f.seek(0)
        df = pd.read_csv(f)
        print(df)
        return
    else:
        pyp.run_pyp(pyp.parse_options(pyp_args))


if __name__ == "__main__":
    run()
