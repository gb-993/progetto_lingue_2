# core/services/logic_parser.py
from __future__ import annotations
from typing import Any
from pyparsing import (
    Word, alphanums, oneOf, Literal, CaselessKeyword, Combine,
    Forward, infixNotation, opAssoc, ParserElement, ParseException
)

ParserElement.enablePackrat()

def build_parser():
    """
    Parser per espressioni booleane su token tri-stato:
      +P  => P vale '+'
      -P  => P vale '-'
      0P  => P vale '0'
    Vincolo: NESSUNO spazio tra segno e parametro (qualsiasi spazio, anche Unicode).
    Operatori: & |  e  AND OR NOT (case-insensitive).  Precedenza: NOT > AND > OR.
    """
    sign = oneOf("+ - 0")
    param = Word(alphanums + "_")

    # Operando: un token unico senza spazi fra segno e parametro
    # (Combine impedisce qualunque whitespace in mezzo, incl. NBSP)
    operand = Combine(sign + param).setParseAction(
        lambda t: (t[0][0], t[0][1:].upper())  # ('+FGM' -> ('+','FGM'))
    )

    expr = Forward()
    NOT = CaselessKeyword("not")
    AND = (Literal("&") | CaselessKeyword("and"))
    OR  = (Literal("|") | CaselessKeyword("or"))

    expr <<= infixNotation(
        operand,
        [
            (NOT, 1, opAssoc.RIGHT),
            (AND, 2, opAssoc.LEFT),
            (OR,  2, opAssoc.LEFT),
        ]
    )
    return expr


def _as_list(node: Any):
    if isinstance(node, tuple):
        return node
    try:
        return list(node)
    except TypeError:
        return node

def eval_node(node, values: dict[str, str]) -> bool:
    # Token foglia: ('+', 'FGM') ecc.
    if isinstance(node, tuple):
        sign, param = node
        return values.get(param) == sign

    node = _as_list(node)

    # NOT <expr>
    if isinstance(node, list) and len(node) == 2 and str(node[0]).lower() == 'not':
        return not eval_node(node[1], values)

    # Catene di AND/OR: [A, op, B, op, C, ...]
    if isinstance(node, list) and len(node) >= 3 and len(node) % 2 == 1:
        # fold-left: ((((A op B) op C) op D) ...)
        result = eval_node(node[0], values)
        i = 1
        while i < len(node):
            op = str(node[i]).lower()
            right = eval_node(node[i + 1], values)
            if op in ('&', 'and'):
                result = result and right
            elif op in ('|', 'or'):
                result = result or right
            else:
                raise ValueError(f"Operatore non gestito: {op}")
            i += 2
        return result

    # Caso binario classico <left> op <right>
    if isinstance(node, list) and len(node) == 3:
        left, op, right = node
        op_str = str(op).lower()
        if op_str in ('&', 'and'):
            return eval_node(left, values) and eval_node(right, values)
        if op_str in ('|', 'or'):
            return eval_node(left, values) or eval_node(right, values)

    raise ValueError(f"Nodo non gestito: {node}")


def evaluate_with_parser(expression: str, values: dict[str, str]) -> bool:
    """
    True se l'espressione è soddisfatta dai valori correnti.
    Robustezza: qualsiasi errore/parse vuoto -> False.
    """
    expr = (expression or "").strip()
    if not expr:
        return True  # condizione vuota = vera

    parser = build_parser()
    try:
        res = parser.parseString(expr, parseAll=True)
        if len(res) == 0:
            return False
        root = _as_list(res[0])
        return eval_node(root, values)
    except Exception:
        return False


# ---------- UTIL per validazione e preview umana ----------

def validate_expression(expression: str) -> None:
    """
    Valida l'espressione. Regole:
      - Nessuno spazio fra segno e parametro (es. '- FGK' o '-\u00A0FGK' = ERRORE).
      - Solo token ammessi (+P, -P, 0P) e operatori (&, |, AND/OR/NOT).
    Solleva ParseException in caso di invalidità.
    """
    parser = build_parser()
    parser.parseString((expression or ""), parseAll=True)


def pretty_print_expression(expression: str) -> str:
    """
    Rende forma human-readable:
      +FGM | +FGA    ->  (FGM=+ OR FGA=+)
      ... & -FGK     ->  ... AND FGK=-
      not +FGM       ->  NOT (FGM=+)
    """
    parser = build_parser()
    try:
        res = parser.parseString((expression or ""), parseAll=True)
        if len(res) == 0:
            raise ParseException("empty parse")
        root = _as_list(res[0])
    except Exception as e:
        raise ParseException(str(e))

    def render(n) -> str:
        if isinstance(n, tuple):
            s, p = n
            return f"{p}={s}"

        n = _as_list(n)

        # NOT <expr>
        if isinstance(n, list) and len(n) == 2 and str(n[0]).lower() == 'not':
            return f"NOT ({render(n[1])})"

        # Catene di AND/OR: [A, op, B, op, C, ...]
        if isinstance(n, list) and len(n) >= 3 and len(n) % 2 == 1:
            # Costruisce una stringa con parentesi complessive per chiarezza
            parts = []
            # primo termine
            parts.append(render(n[0]))
            # coppie (op, termine)
            i = 1
            while i < len(n):
                op_str = str(n[i]).lower()
                op_txt = 'AND' if op_str in ('&', 'and') else ('OR' if op_str in ('|', 'or') else '?')
                parts.append(op_txt)
                parts.append(render(n[i + 1]))
                i += 2
            return "(" + " ".join(parts) + ")"

        # Caso binario classico
        if isinstance(n, list) and len(n) == 3:
            left, op, right = n
            op_str = str(op).lower()
            op_txt = 'AND' if op_str in ('&', 'and') else ('OR' if op_str in ('|', 'or') else '?')
            return f"({render(left)} {op_txt} {render(right)})"

        raise ValueError(f"Nodo non gestito in render: {n}")

    return render(root)