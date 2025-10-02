# core/services/logic_parser.py
from pyparsing import Word, alphanums, oneOf, Literal, Forward, infixNotation, opAssoc, ParserElement

ParserElement.enablePackrat()

def build_parser():
    sign = oneOf("+ - 0")
    param = Word(alphanums + "_")
    operand = (sign + param).setParseAction(lambda t: (t[0], t[1]))

    expr = Forward()
    NOT = Literal("not")
    AND = Literal("&")
    OR = Literal("|")

    expr <<= infixNotation(
        operand,
        [
            (NOT, 1, opAssoc.RIGHT),
            (AND, 2, opAssoc.LEFT),
            (OR, 2, opAssoc.LEFT),
        ]
    )
    return expr

def eval_node(node, values: dict[str, str]):
    if isinstance(node, tuple):
        sign, param = node
        return values.get(param) == sign
    if isinstance(node, list):
        if len(node) == 2 and node[0] == 'not':
            return not eval_node(node[1], values)
        if len(node) == 3:
            left, op, right = node
            if op == '&':
                return eval_node(left, values) and eval_node(right, values)
            elif op == '|':
                return eval_node(left, values) or eval_node(right, values)
    raise ValueError(f"Nodo non gestito: {node}")

def evaluate_with_parser(expression: str, values: dict[str, str]) -> bool:
    if not (expression or "").strip():
        return True  # condizione vuota = vera
    parser = build_parser()
    parsed = parser.parseString(expression, parseAll=True)[0]
    return eval_node(parsed, values)
