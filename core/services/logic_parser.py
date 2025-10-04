# core/services/logic_parser.py
from pyparsing import (
    Word, alphanums, oneOf, Literal,
    Forward, infixNotation, opAssoc, ParserElement, ParseException
)

ParserElement.enablePackrat()

def build_parser():
    # Un operando è: (<segno>, <parametro>)
    # Esempi: +FGM, -FGA, 0SCO
    sign = oneOf("+ - 0")
    param = Word(alphanums + "_")
    operand = (sign + param).setParseAction(lambda t: (t[0], t[1]))

    expr = Forward()
    NOT = Literal("not")   # al momento solo minuscolo, come nel tuo codice
    AND = Literal("&")
    OR  = Literal("|")

    # ATTENZIONE: in pyparsing la precedenza è data dall'ordine delle righe.
    # Qui manteniamo il tuo ordine originale (NOT, poi AND e OR allo stesso livello),
    # per evitare cambi di comportamento inattesi. Se vorrai AND>OR lo facciamo dopo.
    expr <<= infixNotation(
        operand,
        [
            (NOT, 1, opAssoc.RIGHT),
            (AND, 2, opAssoc.LEFT),
            (OR,  2, opAssoc.LEFT),
        ]
    )
    return expr

def _as_list(node):
    """
    Converte in list i ParseResults e, in generale, qualsiasi sequenza non-tuple.
    Lascia intatte le tuple (che rappresentano gli operandi (sign, param)).
    """
    if isinstance(node, tuple):
        return node
    try:
        return list(node)
    except TypeError:
        return node  # foglia non iterabile: lasciamo così

def eval_node(node, values: dict[str, str]):
    """
    Valuta ricorsivamente l'AST prodotto da pyparsing.
    - Operando: tuple (sign, param) => confronto con values[param]
    - Nodo unario: ['not', expr]
    - Nodo binario: [left, '&'|'|', right]
    Nota: i nodi possono arrivare come list o ParseResults: vengono normalizzati.
    """
    # Caso foglia: operando
    if isinstance(node, tuple):
        sign, param = node
        return values.get(param) == sign

    # Normalizza a lista eventuali ParseResults
    node = _as_list(node)

    # Nodi unari: NOT <expr>
    if isinstance(node, list) and len(node) == 2 and str(node[0]).lower() == 'not':
        return not eval_node(node[1], values)

    # Nodi binari: <left> (& or |) <right>
    if isinstance(node, list) and len(node) == 3:
        left, op, right = node
        op_str = str(op)
        if op_str == '&':
            return eval_node(left, values) and eval_node(right, values)
        if op_str == '|':
            return eval_node(left, values) or eval_node(right, values)

    # Se arriviamo qui, la forma non è gestita
    raise ValueError(f"Nodo non gestito: {node}")

def evaluate_with_parser(expression: str, values: dict[str, str]) -> bool:
    """
    True se l'espressione (booleana su +P, -Q, 0R) è soddisfatta dai valori correnti.
    In caso di parsing fallito, torna False (puoi cambiare in log+False).
    """
    if not (expression or "").strip():
        return True  # condizione vuota = vera (comportamento esistente)
    parser = build_parser()
    try:
        # pyparsing ritorna ParseResults; prendiamo l'elemento radice
        parsed_root = parser.parseString(expression, parseAll=True)[0]
        # Normalizziamo il nodo radice per evitare il crash visto
        root = _as_list(parsed_root)
        return eval_node(root, values)
    except ParseException:
        # Espressione invalida => consideriamo FALSA (oppure log e warning in UI)
        return False
