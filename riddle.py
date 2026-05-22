import sys
import argparse
import os
import re

from lark import Lark, Tree, Token, UnexpectedToken, UnexpectedCharacters
from colorama import init, Fore, Style

init(autoreset=True)


class TranspileError(Exception):
    def __init__(self, message, source=None, line=None, column=None, expected=None, category=None):
        super().__init__(message)
        self.source = source
        self.line = line
        self.column = column
        self.expected = expected
        self.category = category

GRAMMAR = r"""
program: statement+

statement: simple_stmt ";"
          | function_def
          | defun_def
          | for_stmt
          | foreach_stmt
          | while_stmt
          | if_stmt
          | block
          | COMMENT
          | bare_stmt ";"
          | namespace_stmt

bare_stmt: NUMBER | STRING | BOOL | NULL | glosure_anon | lambda_anon | array_literal | dict_literal

simple_stmt: assignment
            | expr
            | return_stmt

assignment: expr "=" expr
             | expr "+=" expr           -> add_assign
             | expr "-=" expr           -> sub_assign
             | expr "*=" expr           -> mul_assign
             | expr "/=" expr           -> div_assign
             | expr "^=" expr           -> pow_assign
             | expr "%=" expr           -> mod_assign
             | expr REASSIGN expr       -> reassign

return_stmt: "return" expr

function_def: "function" dotted_name "(" param_list ")" block
defun_def: "defun" dotted_name "(" param_list ")" block

dotted_name: NAME ("." NAME)*

for_stmt: "for" assignment ";" expr ";" (assignment | expr) block
foreach_stmt: "foreach" NAME NAME "in" expr block
while_stmt: "while" expr block

if_stmt: "if" expr block ("else" "if" expr block)* ("else" block)?

namespace_stmt: "namespace" NAME block

block: "{" statement* "}"

?expr: or_expr

?or_expr: and_expr
        | or_expr "||" and_expr       -> or_

?and_expr: cmp_expr
         | and_expr "&&" cmp_expr     -> and_

?cmp_expr: add_expr
         | cmp_expr "<" add_expr      -> lt
         | cmp_expr ">" add_expr      -> gt
         | cmp_expr "<=" add_expr     -> le
         | cmp_expr ">=" add_expr     -> ge
         | cmp_expr "==" add_expr     -> eq
         | cmp_expr "!=" add_expr     -> ne
         | cmp_expr "isa" add_expr    -> isa

?add_expr: mul_expr
         | add_expr "+" mul_expr      -> add
         | add_expr "-" mul_expr      -> sub

?mul_expr: unary_expr
         | mul_expr "*" unary_expr    -> mul
         | mul_expr "/" unary_expr    -> div
         | mul_expr "%" unary_expr    -> mod
         | mul_expr "^" unary_expr    -> pow

?unary_expr: postfix_expr
            | "!" unary_expr           -> not_
            | "-" unary_expr           -> neg
            | "++" unary_expr          -> pre_inc
            | "--" unary_expr          -> pre_dec

postfix_expr: primary
             | postfix_expr "(" arg_list ")"
             | postfix_expr "[" expr "]"
             | postfix_expr "->" NAME "(" arg_list ")"
             | postfix_expr "." NAME
             | postfix_expr "++"       -> post_inc
             | postfix_expr "--"       -> post_dec

primary: NUMBER
       | STRING
       | BOOL
       | NULL
       | NAME
       | glosure_anon
       | lambda_anon
       | array_literal
       | dict_literal
       | "(" expr ")"

glosure_anon: "glosure" "(" param_list ")" block
lambda_anon: "lambda" "(" param_list ")" block

array_literal: "[" _arg_list? "]"
dict_literal: "{" _dict_entries? "}"

_dict_entries: expr ":" expr ("," expr ":" expr)*

# _arg_list is a duplicate of arg_list because Lark cannot inline
# optional [...] rules when used inside another [...] in array_literal
arg_list: [expr ("," expr)*]
_arg_list: [expr ("," expr)*]

param_list: [param ("," param)*]
param: NAME ("=" expr)?

NUMBER: /[0-9]+/
STRING: /"(?:[^"\\]|\\.)*"/
BOOL: "true" | "false"
NULL: "null"
NAME: /[a-zA-Z_][a-zA-Z0-9_!?]*(?:-[a-zA-Z_!?][a-zA-Z0-9_!?\-]*)*/
REASSIGN: /<-/
COMMENT: /\/\/[^\n]*/

%ignore /\s+/
"""

INDENT = "    "

_BINARY_OPS = {
    "add_assign": "(+= {} {})", "sub_assign": "(-= {} {})",
    "mul_assign": "(*= {} {})", "div_assign": "(/= {} {})",
    "pow_assign": "(^= {} {})", "mod_assign": "(%= {} {})",
    "lt": "(< {} {})", "gt": "(> {} {})",
    "le": "(<= {} {})", "ge": "(>= {} {})",
    "eq": "(== {} {})", "ne": "(!= {} {})",
    "add": "(+ {} {})", "sub": "(- {} {})",
    "mul": "(* {} {})", "div": "(/ {} {})",
    "mod": "(% {} {})", "pow": "(^ {} {})",
    "isa": "(isa {} {})",
}
_UNARY_PREFIX_OPS = {
    "not_": "(! {})",
    "pre_inc": "(++ {})", "pre_dec": "(-- {})",
}
_UNARY_POSTFIX_OPS = {
    "post_inc": "(var++ {})", "post_dec": "(var-- {})",
}

_EXPECTED_ALIASES = {
    "__ANON_0": "=", "__ANON_1": "+=", "__ANON_2": "-=", "__ANON_3": "*=",
    "__ANON_4": "/=", "__ANON_5": "^=", "__ANON_6": "%=", "__ANON_7": "||",
    "__ANON_8": "&&", "__ANON_9": "{", "__ANON_10": "}", "__ANON_11": "(",
    "__ANON_12": ")", "__ANON_13": "[", "__ANON_14": "]", "__ANON_15": ":",
    "__ANON_16": ",", "__ANON_17": ";", "__ANON_18": ".", "__ANON_19": "-",
    "LPAR": "(", "RPAR": ")", "LSQB": "[", "RSQB": "]",
    "LESSTHAN": "<", "GREATERTHAN": ">",
    "NUMBER": "<number>", "STRING": "<string>", "NAME": "<name>",
    "BOOL": "<boolean>", "NULL": "null",
    "REASSIGN": "<-", "COMMENT": "<comment>",
}


def _friendly_token(t):
    return _EXPECTED_ALIASES.get(t, t)


class RiddleToGlosure:
    _parser = None

    def __init__(self):
        if RiddleToGlosure._parser is None:
            RiddleToGlosure._parser = Lark(GRAMMAR, parser="earley", lexer="basic", start="program")
        self.parser = RiddleToGlosure._parser
        self._indent = 0
        self._ns_prefixes = []

    def _visit(self, node):
        if isinstance(node, Token):
            return self._visit_token(node)
        data = node.data
        if data in _BINARY_OPS:
            return _BINARY_OPS[data].format(
                self._visit(node.children[0]), self._visit(node.children[1]))
        if data in _UNARY_PREFIX_OPS or data in _UNARY_POSTFIX_OPS:
            table = _UNARY_PREFIX_OPS if data in _UNARY_PREFIX_OPS else _UNARY_POSTFIX_OPS
            return table[data].format(
                self._visit(node.children[0]))
        method = getattr(self, f"_visit_{data}", None)
        if method:
            return method(node)
        raise TranspileError(f"Unknown construct: {data}")

    def _visit_token(self, token):
        if token.type == "NUMBER":
            return token.value
        elif token.type == "STRING":
            return self._escape_string(token.value[1:-1])
        elif token.type == "BOOL":
            return token.value
        elif token.type == "NAME":
            return token.value
        elif token.type == "NULL":
            return "null"
        elif token.type == "COMMENT":
            return ";;" + token.value[2:]
        return str(token)

    def _escape_string(self, s):
        result = []
        i = 0
        while i < len(s):
            if s[i] == "\\" and i + 1 < len(s):
                if s[i + 1] == '"':
                    result.append('"')
                elif s[i + 1] == "\\":
                    result.append("\\\\")
                else:
                    result.append(s[i : i + 2])
                i += 2
            elif s[i] == "'":
                result.append("\\'")
                i += 1
            else:
                result.append(s[i])
                i += 1
        return "'" + "".join(result) + "'"

    def _visit_program(self, node):
        lines = [self._visit(c) for c in node.children]
        return "\n".join(lines)

    def _visit_statement(self, node):
        return self._visit(node.children[0])

    def _visit_bare_stmt(self, node):
        return self._visit(node.children[0])

    def _visit_simple_stmt(self, node):
        return self._visit(node.children[0])

    def _visit_assignment(self, node):
        left, right = node.children
        right_str = self._visit(right)
        if isinstance(left, Tree) and left.data == "postfix_expr":
            c = left.children
            if len(c) == 2:
                if isinstance(c[1], Tree) and c[1].data == "arg_list":
                    raise TranspileError("Cannot assign to a function call")
                if isinstance(c[1], Token) and c[1].type == "NAME":
                    obj = self._visit(c[0])
                    attr = c[1].value
                    return f"(set {obj} '{attr}' {right_str})"
                elif isinstance(c[1], Tree):
                    obj = self._visit(c[0])
                    idx = self._visit(c[1])
                    return f"(set {obj} {idx} {right_str})"
            if len(c) == 1:
                prim = c[0]
                if isinstance(prim, Tree) and prim.data == "primary":
                    ch = prim.children[0]
                    if isinstance(ch, Token):
                        if ch.type in ("NUMBER", "STRING") or ch.value in ("true", "false", "null"):
                            raise TranspileError(f"Cannot assign to a literal: {ch.value}")
                        if self._ns_prefixes and ch.type == "NAME":
                            ns_full = ".".join(self._ns_prefixes)
                            return f"(set {ns_full} '{ch.value}' {right_str})"
                    if isinstance(ch, Tree) and ch.data in ("array_literal", "dict_literal", "glosure_anon", "lambda_anon"):
                        raise TranspileError("Cannot assign to a literal")
        left_str = self._visit(left)
        return f"(def {left_str} {right_str})"

    def _visit_neg(self, node):
        child = node.children[0]
        inner = child
        while isinstance(inner, Tree) and len(inner.children) == 1:
            inner = inner.children[0]
        if isinstance(inner, Token) and inner.type == "NUMBER":
            return "-" + inner.value
        return f"(- {self._visit(child)})"

    def _visit_reassign(self, node):
        # children: [left, REASSIGN_token, right] — named terminal at index 1
        return f"(= {self._visit(node.children[0])} {self._visit(node.children[2])})"

    def _visit_glosure_anon(self, node):
        self._indent += 1
        params_str, body_str = self._make_function_body(node.children[0], node.children[1])
        self._indent -= 1
        return f"(glosure ({params_str}) (begin\n{body_str}))" if body_str else f"(glosure ({params_str}) (begin))"

    def _visit_lambda_anon(self, node):
        self._indent += 1
        params_str, body_str = self._make_function_body(node.children[0], node.children[1])
        self._indent -= 1
        return f"(lambda ({params_str}) (begin\n{body_str}))" if body_str else f"(lambda ({params_str}) (begin))"

    def _visit_return_stmt(self, node):
        return self._visit(node.children[0])

    def _visit_dotted_name(self, node):
        return ".".join(c.value for c in node.children)

    def _make_function_body(self, param_node, block_node):
        param_names = []
        defaults = []
        for child in param_node.children:
            if child is None:
                continue
            p_name = child.children[0].value
            param_names.append(p_name)
            if len(child.children) > 1:
                defaults.append(INDENT * self._indent + f"(defaultvalue {p_name} {self._visit(child.children[1])})")
        params_str = " ".join(param_names)
        body = self._visit(block_node)
        body_lines = defaults[:]
        if body:
            body_lines.append(INDENT * self._indent + body)
        body_str = "\n".join(body_lines)
        return params_str, body_str

    def _make_method(self, keyword, dotted_name, params_str, body_str):
        parts = dotted_name.split(".")
        method_name = parts[-1]
        obj_parts = parts[:-1]
        if len(obj_parts) == 1:
            set_target = obj_parts[0]
        else:
            target = obj_parts[0]
            for part in obj_parts[1:]:
                target = f"(at {target} '{part}')"
            set_target = target
        func_name = f"__{method_name}"
        func_body = f"(begin\n{body_str})" if body_str else "(begin)"
        func_def = f"({keyword} {func_name} ({params_str}) {func_body})"
        set_line = f"(set {set_target} '{method_name}' {func_name})"
        idt = INDENT * self._indent
        return func_def + "\n" + idt + set_line

    def _visit_function_def(self, node):
        name = self._visit(node.children[0])
        if self._ns_prefixes:
            name = ".".join(self._ns_prefixes) + "." + name
        param_node = node.children[1]
        block_node = node.children[2]
        self._indent += 1
        params_str, body_str = self._make_function_body(param_node, block_node)
        self._indent -= 1
        if "." in name:
            return self._make_method("defunction", name, params_str, body_str)
        func_body = f"(begin\n{body_str})" if body_str else "(begin)"
        return f"(defunction {name} ({params_str}) {func_body})"

    def _visit_defun_def(self, node):
        name = self._visit(node.children[0])
        if self._ns_prefixes:
            name = ".".join(self._ns_prefixes) + "." + name
        param_node = node.children[1]
        block_node = node.children[2]
        self._indent += 1
        params_str, body_str = self._make_function_body(param_node, block_node)
        self._indent -= 1
        if "." in name:
            return self._make_method("defun", name, params_str, body_str)
        func_body = f"(begin\n{body_str})" if body_str else "(begin)"
        return f"(defun {name} ({params_str}) {func_body})"

    def _visit_param_list(self, node):
        return " ".join(child.children[0].value for child in node.children)

    def _visit_block(self, node):
        statements = []
        for child in node.children:
            r = self._visit(child)
            if r:
                statements.append(r)
        idt = INDENT * self._indent
        return ("\n" + idt).join(statements)

    def _visit_for_stmt(self, node):
        init, cond, inc, body = node.children
        init_str = self._visit(init)
        cond_str = self._visit(cond)
        inc_str = self._visit(inc)
        self._indent += 1
        body_str = self._visit(body)
        result = f"(for {init_str} {cond_str} {inc_str} (begin\n{INDENT * self._indent}{body_str}))"
        self._indent -= 1
        return result

    def _visit_foreach_stmt(self, node):
        idx = node.children[0].value
        vl = node.children[1].value
        expr_str = self._visit(node.children[2])
        self._indent += 1
        body_str = self._visit(node.children[3])
        result = f"(foreach {idx} {vl} {expr_str} (begin\n{INDENT * self._indent}{body_str}))"
        self._indent -= 1
        return result

    def _visit_while_stmt(self, node):
        cond = self._visit(node.children[0])
        self._indent += 1
        body = self._visit(node.children[1])
        result = f"(while {cond} (begin\n{INDENT * self._indent}{body}))"
        self._indent -= 1
        return result

    def _visit_if_stmt(self, node):
        children = node.children
        cond = self._visit(children[0])
        self._indent += 1
        then_block = self._visit(children[1])
        then_result = f"(if {cond} (begin\n{INDENT * self._indent}{then_block})"
        self._indent -= 1

        if len(children) == 2:
            return then_result + ")"

        remaining = children[2:]
        if len(remaining) % 2 == 1:
            self._indent += 1
            last_block = self._visit(remaining[-1])
            rest = f"(begin\n{INDENT * self._indent}{last_block})"
            self._indent -= 1
            pairs = remaining[:-1]
        else:
            rest = ""
            pairs = remaining

        for i in range(len(pairs) - 2, -1, -2):
            else_cond = self._visit(pairs[i])
            self._indent += 1
            else_block = self._visit(pairs[i + 1])
            else_part = f"(if {else_cond} (begin\n{INDENT * self._indent}{else_block})"
            self._indent -= 1
            if rest:
                rest = f"{else_part}\n{INDENT * self._indent}{rest})"
            else:
                rest = f"{else_part})"

        if rest:
            return f"{then_result}\n{INDENT * self._indent}{rest})"
        return then_result + ")"

    def _visit_namespace_stmt(self, node):
        ns_name = node.children[0].value
        block_node = node.children[1]
        full_name = ".".join(self._ns_prefixes + [ns_name])
        self._ns_prefixes.append(ns_name)
        self._indent += 1
        body = self._visit(block_node)
        result = f"(def {full_name} (dict))"
        if body:
            result += f"\n{INDENT * self._indent}{body}"
        self._indent -= 1
        self._ns_prefixes.pop()
        return result

    def _visit_postfix_expr(self, node):
        children = node.children
        n = len(children)

        if n == 1:
            return self._visit(children[0])
        if n > 3:
            raise TranspileError("Unexpected expression structure")

        if n == 2:
            if isinstance(children[1], Tree) and children[1].data == "arg_list":
                func = self._visit(children[0])
                args = self._visit(children[1])
                if args:
                    return f"({func} {args})"
                return f"({func})"
            if isinstance(children[1], Token) and children[1].type == "NAME":
                obj = self._visit(children[0])
                attr = children[1].value
                return f"(at {obj} '{attr}')"
            obj = self._visit(children[0])
            key = self._visit(children[1])
            return f"(at {obj} {key})"

        if n == 3:
            if isinstance(children[1], Token) and children[1].type == "NAME":
                base = self._visit(children[0])
                method = children[1].value
                args = self._visit(children[2])
                if args:
                    return f"((at {base} '{method}') {base} {args})"
                else:
                    return f"((at {base} '{method}') {base})"
            raise TranspileError("Unexpected expression structure (n==3, middle is not NAME)")

        raise TranspileError(f"Unexpected expression structure (n={n})")

    def _visit_primary(self, node):
        child = node.children[0]
        if isinstance(child, Token):
            if child.type == "STRING":
                return self._escape_string(child.value[1:-1])
            return child.value
        return self._visit(child)

    def _visit_array_literal(self, node):
        items = [self._visit(c) for c in node.children if c is not None]
        if not items:
            return "(array)"
        return f"(array {' '.join(items)})"

    def _visit_dict_literal(self, node):
        children = node.children
        if not children:
            return "(dict)"
        parts = []
        for i in range(0, len(children), 2):
            parts.append(f"{self._visit(children[i])} {self._visit(children[i + 1])}")
        return f"(dict {' '.join(parts)})"

    def _visit_arg_list(self, node):
        args = [self._visit(c) for c in node.children if c is not None]
        return " ".join(args)

    def _collect_chain(self, node, data_name):
        operands = []
        def collect(n):
            if isinstance(n, Tree) and n.data == data_name:
                collect(n.children[0])
                operands.append(self._visit(n.children[1]))
            else:
                operands.append(self._visit(n))
        collect(node)
        return operands

    def _visit_or_(self, node):
        operands = self._collect_chain(node, "or_")
        result = "false"
        for op in reversed(operands):
            result = f"(if {op} true {result})"
        return result

    def _visit_and_(self, node):
        operands = self._collect_chain(node, "and_")
        result = "true"
        for op in reversed(operands):
            result = f"(if {op} {result} false)"
        return result

    def _include_directive(self, match, source_dir, seen):
        path = match.group(1)
        if not os.path.isabs(path):
            path = os.path.normpath(os.path.join(source_dir, path)) if source_dir else path
        if not os.path.exists(path):
            raise TranspileError(f"Included file not found: {path}")
        real = os.path.realpath(path)
        if real in seen:
            raise TranspileError(f"Circular include: '{match.group(1)}' was already included")
        seen.add(real)
        with open(path, "r", encoding="utf-8") as f:
            included = f.read()
        return self._process_includes(included, os.path.dirname(path), seen)

    _INCLUDE_RE = re.compile(r'#include\s+"([^"]+)"\s*;\s*')

    def _process_includes(self, source, source_dir=None, seen=None):
        if seen is None:
            seen = set()
        def repl(m):
            line_start = source.rfind('\n', 0, m.start()) + 1
            prefix = source[line_start:m.start()]
            if '//' in prefix:
                return m.group(0)
            return self._include_directive(m, source_dir, seen)
        return self._INCLUDE_RE.sub(repl, source)

    def _minify_output(self, text):
        lines = []
        for line in text.split("\n"):
            stripped = line.strip()
            if stripped.startswith(";;"):
                continue
            if stripped:
                lines.append(stripped)
        return " ".join(lines)

    def transform(self, source, source_path=None):
        source_dir = os.path.dirname(os.path.abspath(source_path)) if source_path else None
        source = self._process_includes(source, source_dir)
        try:
            tree = self.parser.parse(source)
        except UnexpectedToken as e:
            expected = [_friendly_token(t) for t in e.expected] if hasattr(e, 'expected') else None
            msg = f"Unexpected token '{e.token}'"
            if expected:
                msg += f" — expected {', '.join(expected[:6])}"
                if len(expected) > 6:
                    msg += f", … ({len(expected) - 6} more)"
            raise TranspileError(
                msg, source=source, line=e.line, column=e.column,
                expected=expected, category="Parse Error"
            ) from e
        except UnexpectedCharacters as e:
            msg = f"Unexpected character '{e.char}' at line {e.line}, column {e.column}" if hasattr(e, 'char') else "Unexpected character"
            raise TranspileError(
                msg, source=source, line=e.line, column=e.column,
                category="Parse Error"
            ) from e
        except Exception as e:
            raise TranspileError(
                f"Syntax error: {e}",
                source=source, category="Syntax Error"
            ) from e
        return self._visit(tree)


ATTRIBUTION = """\
;; Hiiiii~ \\(^.^ )
;; This program is written in the Riddle programming language (0.0 )
;; Learn more at https://github.com/shippingfandom/Riddle!
"""


def _print_error(e, file_path=None):
    category = e.category or "Error"
    label = f"  {Fore.RED}{category}{Fore.RESET}"
    print(f"{label} {Fore.YELLOW}{e}{Fore.RESET}", file=sys.stderr)

    if e.line is not None and e.source:
        lines = e.source.splitlines()
        if 1 <= e.line <= len(lines):
            print(file=sys.stderr)
            n = e.line
            start = max(0, n - 3)
            end = min(len(lines), n + 1)
            for i in range(start, end):
                ln = i + 1
                prefix = f"{Fore.RED}>{Fore.RESET}" if ln == n else " "
                num = f"{Fore.CYAN}{ln:>4}{Fore.RESET}"
                print(f"  {prefix} {num} | {lines[i]}", file=sys.stderr)
                if ln == n and e.column is not None:
                    caret = " " * (e.column - 1) + f"{Fore.RED}^{Fore.RESET}"
                    print(f"     {Fore.CYAN}{'':>4}{Fore.RESET} | {caret}", file=sys.stderr)

    if file_path:
        print(f"     {Fore.CYAN}file:{Fore.RESET} {file_path}", file=sys.stderr)

    if e.expected:
        show = e.expected[:6]
        if len(e.expected) > 6:
            show.append(f"… ({len(e.expected) - 6} more)")
        print(f"     {Fore.CYAN}expected:{Fore.RESET} {', '.join(show)}", file=sys.stderr)


def repl():
    transpiler = RiddleToGlosure()
    accumulator = ""

    print(f"  {Fore.GREEN}Riddle REPL{Fore.RESET} — type Riddle code, get Glosure output!")
    print(f"  {Fore.GREEN}//exit{Fore.RESET}, {Fore.GREEN}//quit{Fore.RESET}, {Fore.GREEN}//close{Fore.RESET}, or Ctrl-Z/EOF to quit")
    print()

    LAMBDA_PROMPT = "... "
    PROMPT = ">>> "

    def is_complete(code):
        if not code.strip():
            return False
        in_string = False
        escape = False
        depth = 0
        for ch in code:
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
        if in_string or depth != 0:
            return False
        stripped = code.rstrip()
        return stripped.endswith(";") or stripped.endswith("}")

    while True:
        try:
            prompt = LAMBDA_PROMPT if accumulator else PROMPT
            line = input(prompt)
        except (EOFError, KeyboardInterrupt):
            print()
            break

        accumulator += line + "\n"

        if line.strip() in ("//quit", "//exit", "//close"):
            break

        if not is_complete(accumulator):
            continue

        code = accumulator.strip()
        accumulator = ""

        if code in ("exit", "exit()", "quit", "quit()"):
            break

        try:
            result = transpiler.transform(code)
            print(f"  {Fore.CYAN}{result}{Fore.RESET}")
        except TranspileError as e:
            _print_error(e)
        except Exception as e:
            print(f"  {Fore.RED}Error{Fore.RESET} {Fore.YELLOW}{e}{Fore.RESET}")

    print(f"  {Fore.GREEN}Удачкиии~ .( ^.^)v{Fore.RESET}")


def main():
    parser = argparse.ArgumentParser(
        description="Transpile Riddle source code to Glosure. Run without arguments to start the REPL.",
        epilog="Learn more at https://github.com/shippingfandom/Riddle!",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("input", metavar="<input.riddle>", nargs="?", default=None, help="path to the input Riddle source file")
    parser.add_argument("output", metavar="[output.gls]", nargs="?", default=None, help="optional path to write the transpiled output")
    parser.add_argument("--no-attribution", action="store_true", help="omit the attribution header from the output")
    parser.add_argument("--minify", action="store_true", help="produce minified output without indentation or comments")
    args = parser.parse_args()

    if args.input is None:
        repl()
        return

    try:
        with open(args.input, "r", encoding="utf-8") as f:
            source = f.read()
    except FileNotFoundError:
        print(f"  {Fore.RED}X{Fore.RESET} file not found: {Fore.YELLOW}{args.input}{Fore.RESET}", file=sys.stderr)
        sys.exit(1)

    if not source.strip():
        print(f"  {Fore.RED}X{Fore.RESET} empty input", file=sys.stderr)
        sys.exit(1)

    transpiler = RiddleToGlosure()
    try:
        result = transpiler.transform(source, source_path=args.input)
    except TranspileError as e:
        _print_error(e, file_path=args.input)
        sys.exit(1)

    if not args.no_attribution:
        result = ATTRIBUTION + result

    if args.minify:
        result = transpiler._minify_output(result)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(result)
        print(f"  {Fore.GREEN}Written to{Fore.RESET} {args.output}")
    else:
        sys.stdout.write(result)


if __name__ == "__main__":
    main()
