# NEW: core/management/commands/import_language_from_excel.py

import os
import re

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

# NEW: usiamo openpyxl come in seed_from_csv
try:
    from openpyxl import load_workbook
    HAS_XLSX = True
except Exception:
    HAS_XLSX = False

# NEW: import dei modelli necessari
from core.models import (
    Language,
    ParameterDef,
    Question,
    Answer,
    AnswerStatus,
    Example,
)


# NEW: helper coerenti con seed_from_csv -------------------------
def _coerce_str(x):
    if x is None:
        return None
    return str(x)


def parse_null(v):
    return None if v is None or str(v).strip() == "" else v


def _split_lines(cell_value):
    """
    NEW: normalizza e splitta una cella multilinea in righe pulite.
    """
    if cell_value is None:
        return []
    s = str(cell_value).replace("\r\n", "\n").replace("\r", "\n").strip()
    if not s:
        return []
    return [line.strip() for line in s.split("\n") if line.strip()]


def _split_examples(cell_value):
    """
    NEW: spezza Language_Examples in una lista di (number, textarea).

    Regole:
    - split per newline
    - se la riga inizia con "N." o "N)" (es. "1. foo"), usa N come number e il resto come testo
    - altrimenti usa l'indice (1,2,3,...) come number e l'intera riga come testo
    """
    lines = _split_lines(cell_value)
    out = []
    for idx, line in enumerate(lines):
        m = re.match(r"\s*(\d+)[\.\)]\s*(.*)$", line)
        if m:
            num = m.group(1)
            text = (m.group(2) or "").strip()
        else:
            num = str(idx + 1)
            text = line.strip()
        out.append((num, text))
    return out


# NEW: command principale -----------------------------------------
class Command(BaseCommand):
    help = (
        "Importa Answer ed Example da un file Excel denormalizzato "
        "(es. Database_Chioggia.xlsx), per una singola lingua."
    )

    def add_arguments(self, parser):
        # --file: percorso dell'Excel denormalizzato
        parser.add_argument(
            "--file",
            required=True,
            help="Percorso del file Excel denormalizzato (es. data/Database_Chioggia.xlsx)",
        )
        # --language-name: opzionale, full name della lingua (colonna 'Language')
        parser.add_argument(
            "--language-name",
            dest="language_name",
            help="Full name della lingua (colonna 'Language'); se omesso viene dedotto dal file.",
        )

    def handle(self, *args, **options):
        path = options["file"]
        language_name_opt = options.get("language_name")

        if not HAS_XLSX:
            raise CommandError("openpyxl non disponibile; installalo per usare questo comando.")

        if not os.path.exists(path):
            raise CommandError(f"File non trovato: {path}")

        # NEW: apertura Excel
        wb = load_workbook(path, data_only=True)
        if "Database_model" in wb.sheetnames:
            ws = wb["Database_model"]
        else:
            ws = wb.worksheets[0]

        rows_iter = ws.iter_rows(values_only=True)

        # Header
        try:
            headers = next(rows_iter)
        except StopIteration:
            raise CommandError("File Excel vuoto.")

        headers = [(_coerce_str(h) or "").strip() for h in headers]
        idx = {h: i for i, h in enumerate(headers) if h}

        # NEW: controlliamo che ci siano le colonne minime
        required_cols = ["Language", "Parameter_Label", "Question_ID", "Language_Answer"]
        missing = [c for c in required_cols if c not in idx]
        if missing:
            raise CommandError(
                "Colonne obbligatorie mancanti nel file: " + ", ".join(missing)
            )

        # NEW: carichiamo tutte le righe in memoria e raccogliamo i valori di Language
        all_rows = []
        lang_values = set()

        for raw in rows_iter:
            row_dict = {}
            empty = True
            for h, i in idx.items():
                val = raw[i] if i < len(raw) else None
                if val not in (None, ""):
                    empty = False
                row_dict[h] = val
            if empty:
                continue
            lang_val = row_dict.get("Language")
            if lang_val:
                lang_values.add(str(lang_val).strip())
            all_rows.append(row_dict)

        if not all_rows:
            self.stdout.write(self.style.WARNING("Nessuna riga dati trovata nel file."))
            return

        # NEW: determinazione della lingua
        if language_name_opt:
            language_name = language_name_opt.strip()
            if lang_values and language_name not in lang_values:
                # se non combacia, segnalo subito
                self.stdout.write(
                    self.style.WARNING(
                        f"Valori trovati in colonna 'Language': {sorted(lang_values)}"
                    )
                )
                raise CommandError(
                    f"language_name={language_name!r} non coerente con i dati del file."
                )
        else:
            if len(lang_values) != 1:
                raise CommandError(
                    "Impossibile dedurre in modo univoco la lingua dal file. "
                    f"Valori trovati in 'Language': {sorted(lang_values)}"
                )
            language_name = next(iter(lang_values))

        # NEW: recupero della Language dal DB (per name_full)
        try:
            language = Language.objects.get(name_full__iexact=language_name)
        except Language.DoesNotExist:
            raise CommandError(
                f"Lingua con name_full={language_name!r} non trovata nel DB."
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Import per lingua: {language_name} (id={language.id}) dal file {path}"
            )
        )

        imported_answers = 0
        imported_examples = 0
        skipped_rows = 0

        # NEW: import atomico per sicurezza
        with transaction.atomic():
            for row in all_rows:
                # Filtra per lingua (in caso il file contenga più lingue)
                lang_val = (row.get("Language") or "").strip()
                if lang_val and lang_val != language_name:
                    continue

                param_label = (_coerce_str(row.get("Parameter_Label")) or "").strip()
                if not param_label:
                    skipped_rows += 1
                    continue

                # Trova il parametro esistente
                try:
                    param = ParameterDef.objects.get(id=param_label)
                except ParameterDef.DoesNotExist:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Parametro sconosciuto Parameter_Label={param_label!r}; riga saltata."
                        )
                    )
                    skipped_rows += 1
                    continue

                qid = (_coerce_str(row.get("Question_ID")) or "").strip()
                if not qid:
                    skipped_rows += 1
                    continue

                q_text = parse_null(row.get("Question"))
                q_ex_yes = parse_null(row.get("Question_Examples_YES"))
                q_instr = parse_null(row.get("Question_Intructions_Comments"))

                # NEW: crea la Question se non esiste ancora
                question, created = Question.objects.get_or_create(
                    id=qid,
                    defaults={
                        "parameter": param,
                        "text": q_text or "",
                        "example_yes": q_ex_yes,
                        "instruction": q_instr,
                    },
                )
                if not created and question.parameter_id != param.id:
                    # non tocchiamo domande già collegate ad altri parametri
                    self.stdout.write(
                        self.style.WARNING(
                            f"Question {qid!r} già associata al parametro "
                            f"{question.parameter_id!r}, non a {param_label!r}; riga saltata."
                        )
                    )
                    skipped_rows += 1
                    continue

                # NEW: mappiamo Language_Answer -> "yes"/"no"
                raw_ans = (_coerce_str(row.get("Language_Answer")) or "").strip().upper()
                if raw_ans in ("YES", "Y"):
                    resp = "yes"
                elif raw_ans in ("NO", "N"):
                    resp = "no"
                else:
                    # niente YES/NO => nessuna Answer
                    skipped_rows += 1
                    continue

                comments = parse_null(row.get("Language_Comments"))

                # NEW: create/update dell'Answer
                answer, _ = Answer.objects.update_or_create(
                    language=language,
                    question=question,
                    defaults={
                        "status": AnswerStatus.PENDING,
                        "modifiable": True,
                        "response_text": resp,
                        "comments": comments,
                    },
                )
                imported_answers += 1

                # NEW: rimuoviamo tutti gli Example esistenti per questa Answer
                Example.objects.filter(answer=answer).delete()

                # NEW: ricostruiamo gli Example dalle colonne Language_Examples/Gloss/Translation/References
                ex_main = _split_examples(row.get("Language_Examples"))
                gloss_lines = _split_lines(row.get("Language_Example_Gloss"))
                trans_lines = _split_lines(row.get("Language_Example_Translation"))
                ref_lines = _split_lines(row.get("Language_References"))

                for idx_ex, (num, text_ex) in enumerate(ex_main):
                    gloss = gloss_lines[idx_ex] if idx_ex < len(gloss_lines) else None
                    transl = (
                        trans_lines[idx_ex] if idx_ex < len(trans_lines) else None
                    )
                    ref = ref_lines[idx_ex] if idx_ex < len(ref_lines) else None

                    Example.objects.create(
                        answer=answer,
                        number=num,
                        textarea=text_ex,
                        gloss=parse_null(gloss),
                        translation=parse_null(transl),
                        transliteration=None,
                        reference=parse_null(ref),
                    )
                    imported_examples += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Import completato. Answers creati/aggiornati: {imported_answers}, "
                f"Examples creati: {imported_examples}, righe saltate: {skipped_rows}."
            )
        )
