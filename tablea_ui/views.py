from __future__ import annotations
import csv
import zipfile
from io import BytesIO
from openpyxl import Workbook
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.cluster.hierarchy import linkage, dendrogram
from scipy.spatial.distance import squareform
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render
from core.models import (
    Language, ParameterDef, LanguageParameterEval, Question, Answer,
    ParamSchema, ParamType, ParamLevelOfComparison
)


# --- HELPER: LOGICA DI FILTRO (Il "Cuore" dei dati) ---

def get_tablea_filtered_data(request):
    """Estrae lingue e righe basandosi sui filtri della UI e sui checkbox selezionati."""
    view_mode = request.GET.get("view", "params").strip().lower()

    # 1. Filtro Lingue
    languages = Language.objects.all().order_by("position")
    f_lang_family = request.GET.get("f_lang_family")
    f_lang_top_family = request.GET.get("f_lang_top_family")
    f_lang_grp = request.GET.get("f_lang_grp")
    f_lang_hist = request.GET.get("f_lang_hist")

    if f_lang_top_family: languages = languages.filter(top_level_family=f_lang_top_family)
    if f_lang_family: languages = languages.filter(family=f_lang_family)
    if f_lang_grp: languages = languages.filter(grp=f_lang_grp)
    if f_lang_hist == "yes": languages = languages.filter(historical_language=True)
    if f_lang_hist == "no": languages = languages.filter(historical_language=False)

    languages = list(languages)

    # 2. Filtro Item e Selezione Manuale
    selected_ids = request.GET.getlist("selected_ids")

    if view_mode == "questions":
        items = Question.objects.filter(parameter__is_active=True).select_related("parameter").order_by(
            "parameter__position", "id")
        f_q_template = request.GET.get("f_q_template")
        f_q_stop = request.GET.get("f_q_stop")
        if f_q_template: items = items.filter(template_type=f_q_template)
        if f_q_stop == "yes": items = items.filter(is_stop_question=True)
        if f_q_stop == "no": items = items.filter(is_stop_question=False)
    else:
        items = ParameterDef.objects.filter(is_active=True).order_by("position")
        f_p_schema = request.GET.get("f_p_schema")
        f_p_type = request.GET.get("f_p_type")
        f_p_level = request.GET.get("f_p_level")
        if f_p_schema: items = items.filter(schema=f_p_schema)
        if f_p_type: items = items.filter(param_type=f_p_type)
        if f_p_level: items = items.filter(level_of_comparison=f_p_level)

    if selected_ids:
        items = items.filter(id__in=selected_ids)

    items = list(items)

    # 3. Costruzione Matrice
    matrix = []
    if view_mode == "questions":
        ans_dict = {(a.question_id, a.language_id): a.response_text for a in Answer.objects.filter(question__in=items)}
        for q in items:
            cells = [{"val": (ans_dict.get((q.id, l.id)) or "").upper(), "lang_id": l.id} for l in languages]
            matrix.append({"p": q, "cells": cells})
    else:
        eval_dict = {
            (e.language_parameter.parameter_id, e.language_parameter.language_id): e.value_eval
            for e in LanguageParameterEval.objects.filter(language_parameter__parameter__in=items)
        }
        for p in items:
            cells = [{"val": eval_dict.get((p.id, l.id)) or "", "lang_id": l.id} for l in languages]
            matrix.append({"p": p, "cells": cells})

    return languages, matrix, view_mode


# --- VIEWS: PAGINA PRINCIPALE ED EXPORT STANDARD ---

@login_required
def tablea_index(request):
    languages, rows, view_mode = get_tablea_filtered_data(request)
    ctx_options = {
        "opt_top_families": Language.objects.exclude(top_level_family="").values_list("top_level_family",
                                                                                      flat=True).distinct().order_by(
            "top_level_family"),
        "opt_families": Language.objects.exclude(family="").values_list("family", flat=True).distinct().order_by(
            "family"),
        "opt_groups": Language.objects.exclude(grp="").values_list("grp", flat=True).distinct().order_by("grp"),
        "opt_schemas": ParamSchema.objects.values_list("label", flat=True).order_by("label"),
        "opt_types": ParamType.objects.values_list("label", flat=True).order_by("label"),
        "opt_levels": ParamLevelOfComparison.objects.values_list("label", flat=True).order_by("label"),
        "opt_templates": Question.objects.exclude(template_type="").values_list("template_type",
                                                                                flat=True).distinct().order_by(
            "template_type"),
    }
    return render(request, "tablea/index.html",
                  {**ctx_options, "languages": languages, "rows": rows, "view": view_mode, "params": request.GET})


@login_required
def tablea_export_xlsx(request):
    from openpyxl import Workbook
    languages, rows, view_mode = get_tablea_filtered_data(request)
    wb = Workbook()
    ws = wb.active
    ws.append(["Label", "Name", "Implicational Conditions"] + [l.id for l in languages])
    for r in rows:
        name_val = getattr(r['p'], 'name', getattr(r['p'], 'text', ''))
        impl_val = r['p'].parameter_id if view_mode == "questions" else getattr(r['p'], 'implicational_condition', '')
        ws.append([r['p'].id, name_val, impl_val] + [c['val'] for c in r['cells']])

    buffer = BytesIO()
    wb.save(buffer)
    response = HttpResponse(buffer.getvalue(),
                            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = f'attachment; filename="tableA_{view_mode}.xlsx"'
    return response


@login_required
def tablea_export_csv(request):
    languages, rows, view_mode = get_tablea_filtered_data(request)
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="tableA_{view_mode}_transposed.csv"'
    writer = csv.writer(response)
    writer.writerow(["Language"] + [r['p'].id for r in rows])
    for i, lang in enumerate(languages):
        writer.writerow([lang.id] + [r['cells'][i]['val'] for r in rows])
    return response


# --- ANALISI COMPUTAZIONALE: DISTANZE E DENDROGRAMMA ---

def calc_hamming(p1, p2):
    identities = sum(1 for a, b in zip(p1, p2) if a == b and a in ['+', '-'])
    differences = sum(1 for a, b in zip(p1, p2) if (a == '+' and b == '-') or (a == '-' and b == '+'))
    return differences / (differences + identities) if (differences + identities) > 0 else 0


def calc_jaccard_plus(p1, p2):
    identities = sum(1 for a, b in zip(p1, p2) if a == b == '+')
    differences = sum(1 for a, b in zip(p1, p2) if (a == '+' and b == '-') or (a == '-' and b == '+'))
    return differences / (differences + identities) if (differences + identities) > 0 else 0




# --- NUOVA FUNZIONE PER GENERARE EXCEL ---

def generate_matrix_xlsx(languages, rows, dist_func):
    """Genera un file Excel in memoria contenente la matrice di distanza"""
    wb = Workbook()
    ws = wb.active
    ws.title = "Distance Matrix"

    # Preparazione dei dati (transposizione lingue/parametri)
    lang_data = [[r['cells'][i]['val'] for r in rows] for i in range(len(languages))]

    # Header: "Language" + lista degli ID lingue
    headers = ["Language"] + [l.id for l in languages]
    ws.append(headers)

    # Riempimento delle righe
    for i, l1 in enumerate(languages):
        row_vals = [l1.id]  # Prima colonna: ID della lingua di riga
        for j, l2 in enumerate(languages):
            d = dist_func(lang_data[i], lang_data[j])
            row_vals.append(round(d, 3))
        ws.append(row_vals)

    # Salvataggio nel buffer
    out_buf = BytesIO()
    wb.save(out_buf)
    out_buf.seek(0)
    return out_buf.read()


@login_required
def tablea_export_distances_zip(request):
    view_mode = request.GET.get("view", "params").strip().lower()

    if view_mode != "params":
        return HttpResponse("Distances only for Parameters View", status=400)

    languages, rows, _ = get_tablea_filtered_data(request)

    if not languages or not rows:
        return HttpResponse("No data available", status=400)

    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        # Ora inseriamo file .xlsx invece di .txt
        zf.writestr("distances_hamming.xlsx", generate_matrix_xlsx(languages, rows, calc_hamming))
        zf.writestr("distances_jaccard_plus.xlsx", generate_matrix_xlsx(languages, rows, calc_jaccard_plus))

    buf.seek(0)
    response = HttpResponse(buf.getvalue(), content_type="application/zip")
    response["Content-Disposition"] = 'attachment; filename="distances_excel.zip"'
    return response


@login_required
def tablea_export_dendrogram(request):
    languages, rows, _ = get_tablea_filtered_data(request)
    if not languages: return HttpResponse("No data")

    # Matrice Hamming per il dendrogramma
    lang_data = [[r['cells'][i]['val'] for r in rows] for i in range(len(languages))]
    matrix_data = [[calc_hamming(lang_data[i], lang_data[j]) for j in range(len(languages))] for i in
                   range(len(languages))]

    Z = linkage(squareform(matrix_data), method='average')

    plt.figure(figsize=(10, 8))
    dendrogram(Z, labels=[l.id for l in languages], orientation='left')
    plt.title("Dendrogram UPGMA (Hamming)")
    plt.tight_layout()

    img_buf = BytesIO()
    plt.savefig(img_buf, format='png', dpi=300)
    plt.close()
    img_buf.seek(0)

    response = HttpResponse(img_buf.read(), content_type="image/png")
    response["Content-Disposition"] = 'attachment; filename="dendrogram_upgma.png"'
    return response