import inspect
import logging
import re
from functools import lru_cache
from typing import Optional, List

import pygments
from pygments.token import Token

from csv_eval.lexer_and_parser import (
    AssignmentState,
    AccessorConvert,
    lexer,
    regex_like_raw_str,
    regex_pythonic_slice,
)
from csv_eval.utils import FIELD_VAR_NAME, ExpandableList

LOGGER = logging.getLogger(__file__)


class Transpiler:
    def __init__(
            self,
            select_field: Optional[str],
            has_header: bool,
            use_auto_quote: bool,
            filter_str: Optional[str],
    ):
        self._print_field_statement = None
        self.select_field = select_field
        self.has_header = has_header
        self.filter_str = filter_str
        self.use_auto_quote = use_auto_quote
        self.extra_headers = []

    @lru_cache
    def get_print_field_statement(self):
        if self.select_field is not None:
            fields_idx_to_print = self.select_field.split(",")

            if self.use_auto_quote:
                fields_idx_to_print = (self.auto_quote(s) for s in fields_idx_to_print)
            _collected_print_statement = ",".join(
                f"{FIELD_VAR_NAME}[{i}]" for i in fields_idx_to_print
            )
            _print_field_statement = (
                f"print({collect_output_fields.__name__}"
                f"({_collected_print_statement}))"
            )
        else:
            _print_field_statement = f"print({FIELD_VAR_NAME})"
        return _print_field_statement

    def auto_quote(self, string):
        if self.use_auto_quote:
            if not re.match(f"^{regex_pythonic_slice}$", string):
                return f"'{string}'"
        return string

    def add_extra_headers(self, extra_headers):
        self.extra_headers = extra_headers

    def get_pyp_args(self):
        pyp_args = [
            "-b",
            inspect.getsource(ExpandableList),
        ]
        if self.select_field is not None:
            pyp_args.extend(["-b", inspect.getsource(collect_output_fields)])
        if len(self.extra_headers) > 0:
            pyp_args.extend(
                [
                    "-b",
                    f"{ExpandableList.__name__}."
                    f"{ExpandableList.add_extra_headers.__name__}("
                    f"{self.extra_headers})",
                ]
            )

        return pyp_args

    def transpile(self, preprocessed_statements: str):
        is_header_input = "i==0" if self.has_header else "False"
        return f"""\
{FIELD_VAR_NAME}={ExpandableList.__name__}(x.split(','), is_header={is_header_input});
{self.get_header_logic()}
{self.get_filter_logic()}
{preprocessed_statements}
{self.get_print_field_statement()}
"""

    def get_header_logic(self):
        """
        if there is header, skip the csv eval for the header row
        :return:
        """
        if self.has_header:
            return f"if i == 0: {self.get_print_field_statement()}; continue"
        return ""

    def get_filter_logic(self):
        if self.filter_str is None:
            return ""
        content = preprocess_field_only(
            self.filter_str, use_auto_quote=self.use_auto_quote
        )
        return f"if not ({content}): continue"


def extract_last_referenced_field(state: AssignmentState) -> str:
    assert state.last_field_num is not None
    if state.last_accessor_convert is AccessorConvert.NoOp:
        access_caster = ""
    elif state.last_accessor_convert is AccessorConvert.AsStr:
        access_caster = ".as_str"
    elif state.last_accessor_convert is AccessorConvert.AsFloat:
        access_caster = ".as_float"
    elif state.last_accessor_convert is AccessorConvert.AsInt:
        access_caster = ".as_int"
    else:
        raise RuntimeError(state.last_accessor_convert, f"{FIELD_VAR_NAME}{state.last_field_num}")

    out = f"{FIELD_VAR_NAME}{access_caster}{state.last_field_num}"
    state.clear_referenced_field()
    return out


def _process_accessor_token(content: str, state: AssignmentState):
    if content.startswith("s"):
        state.last_accessor_convert = AccessorConvert.AsStr
    elif content.startswith("f"):
        state.last_accessor_convert = AccessorConvert.AsFloat
    elif content.startswith("i"):
        state.last_accessor_convert = AccessorConvert.AsInt
    elif content.startswith("x"):
        state.last_accessor_convert = AccessorConvert.NoOp
    else:
        raise NotImplementedError(f"accessor token is not defined for {content}")

    state.last_field_num = content[1:]
    return state


def preprocess_full_statements(
        statement: str, use_auto_quote: bool
) -> [str, List[str]]:
    """
    Preprocess any number of statement, including assignment statement.
    :param statement:
    :param use_auto_quote:
    :return:
    """
    transpiled_code = ""

    new_cols_headers = []
    if statement is not None:
        state = AssignmentState()
        for token, content in pygments.lex(statement, lexer):
            if token is Token.Text.Whitespace:
                continue
            LOGGER.debug("Visit token %s with content %s", token, content)
            if token is Token.AccessorLookLikeRawStr:
                if use_auto_quote:
                    content = replace_raw_string_inside_square_bracket(content)

                # process it again as token accessor
                token = Token.Accessor

            if token is Token.Accessor:
                _process_accessor_token(content, state)

            elif token is Token.AccessorAppend:
                new_cols_headers.append(f"_{len(new_cols_headers) + 1}")
                state.last_field_num = f"['{new_cols_headers[-1]}']"
                state.last_accessor_convert = AccessorConvert.NoOp

            elif token is Token.AssignmentOperator:
                transpiled_code += f"{FIELD_VAR_NAME}{state.last_field_num}"
                transpiled_code += "="
                if content != "=":
                    # cast
                    transpiled_code += extract_last_referenced_field(state)
                    # perform operation
                    transpiled_code += content[0:1]
                else:
                    state.clear_referenced_field()
                state.at_lvalue = False

            elif token is Token.StatementSep:
                state.at_lvalue = True
                transpiled_code += content

            else:
                if not state.at_lvalue:
                    if state.last_field_num is not None:
                        transpiled_code += extract_last_referenced_field(state)
                transpiled_code += content

            # last_token = token
    return transpiled_code, new_cols_headers


def preprocess_field_only(statement: str, use_auto_quote: bool) -> [str, List[str]]:
    """
    Preprocess that is designed only for condition expression
    :param statement:
    :param use_auto_quote:
    :return:
    """
    preprocessed_code = ""

    state = AssignmentState()
    for token, content in pygments.lex(statement, lexer):
        if token is Token.Text.Whitespace:
            continue
        LOGGER.debug("Visit token %s with content %s", token, content)
        if token is Token.AccessorLookLikeRawStr:
            if use_auto_quote:
                content = replace_raw_string_inside_square_bracket(content)
            token = Token.Accessor
            # process it again as token accessor

        if token is Token.Accessor:
            _process_accessor_token(content, state)
            preprocessed_code += extract_last_referenced_field(state)
        else:
            preprocessed_code += content
    return preprocessed_code


def collect_output_fields(*fields_to_print) -> str:
    from typing import Iterable

    out = []
    for field in fields_to_print:
        if isinstance(field, Iterable) and not isinstance(field, str):
            out.extend(field)
        else:
            out.append(field)
    return ",".join(map(str, out))


def replace_raw_string_inside_square_bracket(content):
    return re.sub(
        r"\[(" + regex_like_raw_str + r")\]",
        r"['\g<1>']",
        content,
    )
