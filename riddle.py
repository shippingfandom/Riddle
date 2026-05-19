import sys
import argparse

from lark import Lark, Tree, Token, UnexpectedToken, UnexpectedCharacters
from colorama import init, Fore, Style

init(autoreset=True)


class TranspileError(Exception):
    def __init__(self, message, source=None, line=None, column=None):
        super().__init__(message)
        self.source = source
        self.line = line
        self.column = column

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

for_stmt: "for" assignment ";" expr ";" assignment block
foreach_stmt: "foreach" NAME NAME "in" expr block
while_stmt: "while" expr block

if_stmt: "if" expr block ("else" "if" expr block)* ("else" block)?

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


class RiddleToGlosure:
    _parser = None

    def __init__(self):
        if RiddleToGlosure._parser is None:
            RiddleToGlosure._parser = Lark(GRAMMAR, parser="earley", lexer="basic", start="program")
        self.parser = RiddleToGlosure._parser

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
        params_str, body_str = self._make_function_body(node.children[0], node.children[1])
        return f"(glosure ({params_str}) (begin\n{body_str}))" if body_str else f"(glosure ({params_str}) (begin))"

    def _visit_lambda_anon(self, node):
        params_str, body_str = self._make_function_body(node.children[0], node.children[1])
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
                defaults.append(INDENT + f"(defaultvalue {p_name} {self._visit(child.children[1])})")
        params_str = " ".join(param_names)
        body = self._visit(block_node)
        body_lines = defaults[:]
        if body:
            body_lines.append(INDENT + body)
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
        func_def = f"({keyword} {func_name} ({params_str}) (begin\n{body_str}))"
        set_line = f"(set {set_target} '{method_name}' {func_name})"
        return func_def + "\n" + set_line

    def _visit_function_def(self, node):
        name = self._visit(node.children[0])
        param_node = node.children[1]
        block_node = node.children[2]
        params_str, body_str = self._make_function_body(param_node, block_node)
        if "." in name:
            return self._make_method("defunction", name, params_str, body_str)
        return f"(defunction {name} ({params_str}) (begin\n{body_str}))"

    def _visit_defun_def(self, node):
        name = self._visit(node.children[0])
        param_node = node.children[1]
        block_node = node.children[2]
        params_str, body_str = self._make_function_body(param_node, block_node)
        if "." in name:
            return self._make_method("defun", name, params_str, body_str)
        return f"(defun {name} ({params_str}) (begin\n{body_str}))"

    def _visit_param_list(self, node):
        return " ".join(child.children[0].value for child in node.children)

    def _visit_block(self, node):
        statements = []
        for child in node.children:
            r = self._visit(child)
            if r:
                statements.append(r)
        return ("\n" + INDENT).join(statements)

    def _visit_for_stmt(self, node):
        init, cond, inc, body = node.children
        init_str = self._visit(init)
        cond_str = self._visit(cond)
        inc_str = self._visit(inc)
        body_str = self._visit(body)
        return f"(for {init_str} {cond_str} {inc_str} (begin\n{INDENT}{body_str}))"

    def _visit_foreach_stmt(self, node):
        idx = node.children[0].value
        vl = node.children[1].value
        expr_str = self._visit(node.children[2])
        body_str = self._visit(node.children[3])
        return f"(foreach {idx} {vl} {expr_str} (begin\n{INDENT}{body_str}))"

    def _visit_while_stmt(self, node):
        cond = self._visit(node.children[0])
        body = self._visit(node.children[1])
        return f"(while {cond} (begin\n{INDENT}{body}))"

    def _visit_if_stmt(self, node):
        children = node.children
        cond = self._visit(children[0])
        then_block = self._visit(children[1])

        if len(children) == 2:
            return f"(if {cond} (begin\n{INDENT}{then_block}))"

        remaining = children[2:]
        if len(remaining) % 2 == 1:
            last_block = self._visit(remaining[-1])
            result = f"(begin\n{INDENT}{last_block})"
            pairs = remaining[:-1]
        else:
            result = ""
            pairs = remaining

        for i in range(len(pairs) - 2, -1, -2):
            else_cond = self._visit(pairs[i])
            else_block = self._visit(pairs[i + 1])
            if result:
                result = f"(if {else_cond} (begin\n{INDENT}{else_block})\n{result})"
            else:
                result = f"(if {else_cond} (begin\n{INDENT}{else_block}))"

        return f"(if {cond} (begin\n{INDENT}{then_block})\n{result})"

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

    def transform(self, source):
        try:
            tree = self.parser.parse(source)
        except UnexpectedToken as e:
            raise TranspileError(
                f"Unexpected token '{e.token}'",
                source=source, line=e.line, column=e.column
            ) from e
        except UnexpectedCharacters as e:
            raise TranspileError(
                f"Unexpected character",
                source=source, line=e.line, column=e.column
            ) from e
        except Exception as e:
            raise TranspileError(
                f"Syntax error: {e}",
                source=source
            ) from e
        return self._visit(tree)


ATTRIBUTION = """\
;; Hiiiii~ \\(^.^ )
;; This program is written in the Riddle programming language (0.0 )
;; Learn more at https://github.com/shippingfandom/Riddle!
"""


def main():
    parser = argparse.ArgumentParser(
        description="Transpile Riddle source code to Glosure.",
        epilog="Learn more at https://github.com/shippingfandom/Riddle!",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("input", metavar="<input.riddle>", help="path to the input Riddle source file")
    parser.add_argument("output", metavar="[output.gls]", nargs="?", default=None, help="optional path to write the transpiled output")
    parser.add_argument("--no-attribution", action="store_true", help="omit the attribution header from the output")
    args = parser.parse_args()

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
        result = transpiler.transform(source)
    except TranspileError as e:
        print(f"  {Fore.RED}X{Fore.RESET} {Fore.YELLOW}{e}{Fore.RESET}", file=sys.stderr)
        if e.line is not None and e.source:
            lines = e.source.splitlines()
            if 1 <= e.line <= len(lines):
                print(file=sys.stderr)
                print(f"    {Fore.CYAN}{e.line:>4}{Fore.RESET} | {lines[e.line - 1]}", file=sys.stderr)
                if e.column is not None:
                    print(f"    {Fore.CYAN}{'':>4}{Fore.RESET} | {' ' * (e.column - 1)}{Fore.RED}^{Fore.RESET}", file=sys.stderr)
        sys.exit(1)

    if not args.no_attribution:
        result = ATTRIBUTION + result

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(result)
        print(f"  {Fore.GREEN}Written to{Fore.RESET} {args.output}")
    else:
        sys.stdout.write(result)


if __name__ == "__main__":
    main()
