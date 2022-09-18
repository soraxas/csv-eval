from dataclasses import dataclass
from enum import Enum
from typing import Optional

from pygments.lexer import RegexLexer
from pygments.token import Token

regex_like_raw_str = r"[^'\"\]]+"
regex_pythonic_slice = r"[0-9:-]+"


class CsvEvalLexer(RegexLexer):
    name = "CsvEvalLang"

    tokens = {
        "root": [
            (r"[sfix]\[[ ]*\+[ ]*\]", Token.AccessorAppend),
            (r"[sfix]\[" f"{regex_pythonic_slice}" r"\]", Token.Accessor),
            (r"[sfix]\[" f"{regex_like_raw_str}" r"\]", Token.AccessorLookLikeRawStr),
            (r"[sfix]\[[^]]+]", Token.Accessor),
            (r"[+*/-]?=", Token.AssignmentOperator),
            (r";", Token.StatementSep),
            # (r'.*', Token.PassThrough),
        ],
    }


lexer = CsvEvalLexer()


class AccessorConvert(Enum):
    AsStr = 1
    AsFloat = 2
    AsInt = 3
    NoOp = 4


@dataclass
class AssignmentState:
    last_accessor_convert: Optional[AccessorConvert] = None
    last_field_num: Optional[str] = None

    at_lvalue: bool = True

    def clear_referenced_field(self):
        self.last_field_num = None
        self.last_accessor_convert = None
