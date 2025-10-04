# core/services/logic_parser.py
from __future__ import annotations
from typing import Any
from pyparsing import (
    Word, alphanums, oneOf, Literal, CaselessKeyword, White,
    Forward, infixNotation, opAssoc, ParserElement, ParseException
)

ParserElement.enablePackrat()


def build_parser():
    """
    Parser per espressioni booleane su token tri-stato:
      +P  => P vale '+'
      -P  => P vale '-'
      0P  => P vale '0'
    Vincolo: nessuno spazio tra segno e parametro (es. '-FGK' OK, '- FGK' ERRORE).
    Operatori supportati (entrambi): & |  e  AND OR NOT (case-insensitive).
    Precedenza: NOT > AND > OR.
    """
    # Operando: <segno><param> SENZA spazi interni
    sign = oneOf("+ - 0")
    param = Word(alphanums + "_")
    # Rifiuta spazi fra segno e parametro
    operand = (sign + ~White() + param).setParseAction(
        lambda t: (t[0], t[2].upper())   # normalizza IDs a MAIUSCOLO
    )

    expr = Forward()

    NOT = CaselessKeyword("not")
    AND = (Literal("&") | CaselessKeyword("and"))
    OR  = (Literal("|") | CaselessKeyword("or"))

    # Ordine delle righe = dalla precedenza più alta alla più bassa
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
    """Converte ParseResults in list; lascia intatte le tuple (operandi)."""
    if isinstance(node, tuple):
        return node
    try:
        return list(node)
    except TypeError:
        return node


def eval_node(node, values: dict[str, str]) -> bool:
    """
    Valuta ricorsivamente l'AST:
      - Operando: tuple (sign, PARAM)
      - Unario:   ['not', expr]
      - Binario:  [left, op, right] con op in {'&','|','and','or'} (case-insensitive)
    """
    if isinstance(node, tuple):
        sign, param = node
        return values.get(param) == sign

    node = _as_list(node)

    # NOT <expr>
    if isinstance(node, list) and len(node) == 2 and str(node[0]).lower() == 'not':
        return not eval_node(node[1], values)

    # <left> (AND/OR) <right>
    if isinstance(node, list) and len(node) == 3:
        left, op, right = node
        op_str = str(op).lower()
        if op_str in ('&', 'and'):
            return eval_node(left, values) and eval_node(right, values)
        if op_str in ('|', 'or'):
            return eval_node(left, values) or eval_node(right, values)

    raise ValueError(f"Nodo non gestito: {node}")


from pyparsing import ParseException

def evaluate_with_parser(expression: str, values: dict[str, str]) -> bool:
    """
    True se l'espressione è soddisfatta dai valori correnti.
    Robustezza: se parsing fallisce o produce 0 elementi, ritorna False.
    """
    expr = (expression or "").strip()
    if not expr:
        return True  # condizione vuota = vera

    parser = build_parser()
    try:
        res = parser.parseString(expr, parseAll=True)
    except ParseException:
        return False  # oppure: loggare e poi False

    if len(res) == 0:
        return False  # evita IndexError

    root = _as_list(res[0])
    try:
        return eval_node(root, values)
    except Exception:
        # Qualsiasi altra forma imprevista -> prudenzialmente False
        return False



# ---------- UTIL per validazione e preview umana ----------

def validate_expression(expression: str) -> None:
    """
    Valida l'espressione. Regole:
      - Nessuno spazio fra segno e parametro (es. '- FGK' è ERRORE).
      - Solo token ammessi (+P, -P, 0P) e operatori (&, |, AND/OR/NOT).
    Solleva ParseException in caso di invalidità.
    """
    parser = build_parser()
    # Questo parse fallirà se ci sono spazi vietati o token non ammessi
    parser.parseString((expression or ""), parseAll=True)


def pretty_print_expression(expression: str) -> str:
    """
    Ritorna una rappresentazione canonica "umana":
      +FGM | +FGA  ->  (FGM=+ OR FGA=+)
      ... & -FGK   ->  ... AND FGK=-
      not +FGM     ->  NOT (FGM=+)
    Mantiene le parentesi per preservare la struttura.
    Solleva ParseException se l'espressione è invalida.
    """
    parser = build_parser()
    root = _as_list(parser.parseString((expression or ""), parseAll=True)[0])

    def render(n) -> str:
        if isinstance(n, tuple):
            s, p = n
            return f"{p}={s}"
        n = _as_list(n)
        if isinstance(n, list) and len(n) == 2 and str(n[0]).lower() == 'not':
            return f"NOT ({render(n[1])})"
        if isinstance(n, list) and len(n) == 3:
            left, op, right = n
            op_str = str(op).lower()
            if op_str in ('&', 'and'):
                op_txt = 'AND'
            elif op_str in ('|', 'or'):
                op_txt = 'OR'
            else:
                raise ValueError(f"Operatore non gestito in render: {op}")
            return f"({render(left)} {op_txt} {render(right)})"
        raise ValueError(f"Nodo non gestito in render: {n}")

    return render(root)
