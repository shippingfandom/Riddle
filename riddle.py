from lark import Lark, Tree, Token, UnexpectedToken, UnexpectedCharacters


class TranspileError(Exception):
    pass

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

simple_stmt: assignment
            | expr
            | return_stmt

assignment: expr "=" expr

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

postfix_expr: primary
            | postfix_expr "(" arg_list ")"
            | postfix_expr "[" expr "]"
            | postfix_expr "->" NAME "(" arg_list ")"
            | postfix_expr "." NAME

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

_dict_entries: STRING ":" expr ("," STRING ":" expr)*

arg_list: [expr ("," expr)*]
_arg_list: [expr ("," expr)*]

param_list: [param ("," param)*]
param: NAME ("=" expr)?

NUMBER: /[0-9]+/
STRING: /"[^"]*"/
BOOL: "true" | "false"
NULL: "null"
NAME: /[a-zA-Z_][a-zA-Z0-9_!?]*(?:-[a-zA-Z_!?][a-zA-Z0-9_!?\-]*)*/
COMMENT: /\/\/[^\n]*/

%ignore /\s+/
"""

INDENT = "    "


class RiddleToGlosure:
    def __init__(self):
        self.parser = Lark(GRAMMAR, parser="earley", lexer="basic", start="program")

    def _visit(self, node):
        if isinstance(node, Token):
            return self._visit_token(node)
        method = getattr(self, f"_visit_{node.data}", None)
        if method:
            return method(node)
        raise TranspileError(f"Unknown construct: {node.data}")

    def _visit_token(self, token):
        if token.type == "NUMBER":
            return token.value
        elif token.type == "STRING":
            return "'" + token.value[1:-1] + "'"
        elif token.type == "BOOL":
            return token.value
        elif token.type == "NAME":
            return token.value
        elif token.type == "NULL":
            return "null"
        elif token.type == "COMMENT":
            return ";;" + token.value[2:]
        return str(token)

    def _visit_program(self, node):
        lines = [self._visit(c) for c in node.children]
        return "\n".join(lines)

    def _visit_statement(self, node):
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

    def _visit_glosure_anon(self, node):
        params_str, body_str = self._make_function_body(node.children[0], node.children[1])
        return f"(glosure ({params_str}) (begin\n{body_str}))"

    def _visit_lambda_anon(self, node):
        params_str, body_str = self._make_function_body(node.children[0], node.children[1])
        return f"(lambda ({params_str}) (begin\n{body_str}))"

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
                return "'" + child.value[1:-1] + "'"
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
            key = "'" + children[i].value[1:-1] + "'"
            val = self._visit(children[i + 1])
            parts.append(f"{key} {val}")
        return f"(dict {' '.join(parts)})"

    def _visit_arg_list(self, node):
        args = [self._visit(c) for c in node.children if c is not None]
        return " ".join(args)

    def _visit_or_(self, node):
        return f"(| {self._visit(node.children[0])} {self._visit(node.children[1])})"

    def _visit_and_(self, node):
        return f"(& {self._visit(node.children[0])} {self._visit(node.children[1])})"

    def _visit_lt(self, node):
        return f"(< {self._visit(node.children[0])} {self._visit(node.children[1])})"

    def _visit_gt(self, node):
        return f"(> {self._visit(node.children[0])} {self._visit(node.children[1])})"

    def _visit_le(self, node):
        return f"(<= {self._visit(node.children[0])} {self._visit(node.children[1])})"

    def _visit_ge(self, node):
        return f"(>= {self._visit(node.children[0])} {self._visit(node.children[1])})"

    def _visit_eq(self, node):
        return f"(== {self._visit(node.children[0])} {self._visit(node.children[1])})"

    def _visit_ne(self, node):
        return f"(!= {self._visit(node.children[0])} {self._visit(node.children[1])})"

    def _visit_add(self, node):
        return f"(+ {self._visit(node.children[0])} {self._visit(node.children[1])})"

    def _visit_sub(self, node):
        return f"(- {self._visit(node.children[0])} {self._visit(node.children[1])})"

    def _visit_mul(self, node):
        return f"(* {self._visit(node.children[0])} {self._visit(node.children[1])})"

    def _visit_div(self, node):
        return f"(/ {self._visit(node.children[0])} {self._visit(node.children[1])})"

    def _visit_mod(self, node):
        return f"(% {self._visit(node.children[0])} {self._visit(node.children[1])})"

    def _visit_pow(self, node):
        return f"(^ {self._visit(node.children[0])} {self._visit(node.children[1])})"

    def _visit_isa(self, node):
        return f"(isa {self._visit(node.children[0])} {self._visit(node.children[1])})"

    def _visit_not_(self, node):
        return f"(! {self._visit(node.children[0])})"

    def _visit_neg(self, node):
        return f"(- {self._visit(node.children[0])})"

    def transform(self, source):
        try:
            tree = self.parser.parse(source)
        except UnexpectedToken as e:
            raise TranspileError(
                f"Unexpected token '{e.token}' at line {e.line}, column {e.column}"
            ) from e
        except UnexpectedCharacters as e:
            raise TranspileError(
                f"Unexpected character at line {e.line}, column {e.column}"
            ) from e
        except Exception as e:
            raise TranspileError(f"Syntax error: {e}") from e
        return self._visit(tree)


ATTRIBUTION = """\
;; Hiiiii~ \\(^.^ )
;; This program is written in the Riddle programming language (0.0 )
;; Learn more at https://github.com/shippingfandom/Riddle!
"""


def main():
    import sys
    argv = [a for a in sys.argv[1:] if a != "--no-attribution"]
    show_attribution = "--no-attribution" not in sys.argv[1:]

    if not argv:
        print("Usage: python riddle.py [--no-attribution] <input.riddle> [output.gls]", file=sys.stderr)
        sys.exit(1)

    try:
        with open(argv[0], "r", encoding="utf-8") as f:
            source = f.read()
    except FileNotFoundError:
        print(f"File not found: {argv[0]}", file=sys.stderr)
        sys.exit(1)

    if not source.strip():
        print("Error: empty input", file=sys.stderr)
        sys.exit(1)

    transpiler = RiddleToGlosure()
    try:
        result = transpiler.transform(source)
    except TranspileError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if show_attribution:
        result = ATTRIBUTION + result

    if len(argv) >= 2:
        with open(argv[1], "w", encoding="utf-8") as f:
            f.write(result)
        print(f"Written to {argv[1]}")
    else:
        sys.stdout.write(result)


if __name__ == "__main__":
    main()
