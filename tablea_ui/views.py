from __future__ import annotations
import csv
import zipfile
from io import BytesIO
from io import StringIO
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
    f_lang_specific = request.GET.getlist("f_lang_specific")


    if f_lang_top_family: languages = languages.filter(top_level_family=f_lang_top_family)
    if f_lang_family: languages = languages.filter(family=f_lang_family)
    if f_lang_grp: languages = languages.filter(grp=f_lang_grp)
    if f_lang_hist == "yes": languages = languages.filter(historical_language=True)
    if f_lang_hist == "no": languages = languages.filter(historical_language=False)
    if f_lang_specific: languages = languages.filter(id__in=f_lang_specific)
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
        "opt_top_families": Language.objects.exclude(top_level_family="").values_list("top_level_family",flat=True).distinct().order_by("top_level_family"),
        "opt_families": Language.objects.exclude(family="").values_list("family", flat=True).distinct().order_by("family"),
        "opt_groups": Language.objects.exclude(grp="").values_list("grp", flat=True).distinct().order_by("grp"),
        "opt_schemas": ParamSchema.objects.values_list("label", flat=True).order_by("label"),
        "opt_types": ParamType.objects.values_list("label", flat=True).order_by("label"),
        "opt_levels": ParamLevelOfComparison.objects.values_list("label", flat=True).order_by("label"),
        "opt_templates": Question.objects.exclude(template_type="").values_list("template_type",flat=True).distinct().order_by("template_type"),
        "opt_all_languages": Language.objects.all().order_by("name_full"),
        "selected_specific_langs": request.GET.getlist("f_lang_specific"),
    }
    return render(request, "tablea/index.html",
                  {**ctx_options, "languages": languages, "rows": rows, "view": view_mode, "params": request.GET})

@login_required
def tablea_export_xlsx(request):
    from openpyxl import Workbook
    languages, rows, view_mode = get_tablea_filtered_data(request)
    wb = Workbook()
    ws = wb.active
    ws.append(["Label", "Question_text", "Implicational Condition(s)"] + [l.id for l in languages])
    for r in rows:
        name_val = getattr(r['p'], 'name', getattr(r['p'], 'text', ''))
        impl_val = r['p'].parameter_id if view_mode == "questions" else getattr(r['p'], 'implicational_condition', '')
        ws.append([r['p'].id, name_val, impl_val] + [c['val'] for c in r['cells']])

    buffer = BytesIO()
    wb.save(buffer)
    response = HttpResponse(buffer.getvalue(),content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = f'attachment; filename="tableA_{view_mode}.xlsx"'
    return response

# la versione del download per question (senza Implicatoinal condition)
@login_required
def tablea_export_questions_xlsx(request):
    from openpyxl import Workbook
    languages, rows, view_mode = get_tablea_filtered_data(request)

    wb = Workbook()
    ws = wb.active

    ws.append(["Label", "Question_text"] + [l.id for l in languages])

    for r in rows:
        # Recuperiamo il testo della domanda
        name_val = getattr(r['p'], 'text', getattr(r['p'], 'name', ''))

        # Aggiungiamo la riga: ID, Nome, e poi direttamente le celle delle lingue
        ws.append([r['p'].id, name_val] + [c['val'] for c in r['cells']])

    buffer = BytesIO()
    wb.save(buffer)
    response = HttpResponse(buffer.getvalue(),
                            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = 'attachment; filename="tableA_questions.xlsx"'
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


def hamming_core(P1, P2):
    id = 0.0
    dif = 0.0
    for i in range(len(P1)):
        # identities are counted on '+', and '-'
        if P1[i] == P2[i] == "+" or P1[i] == P2[i] == "-":
            id += 1
        # differences include all mismatches among '+' and '-', other symbols are ignored
        elif (P1[i] == "+" and P2[i] == "-") or (P1[i] == "-" and P2[i] == "+"):
            dif += 1
    return dif / (dif + id) if (dif + id) > 0 else 0.0


def jaccard_core(P1, P2, identity="+"):
    id = 0.0
    dif = 0.0
    for i in range(len(P1)):
        # identities are counted ONLY on the chosen symbol
        if P1[i] == P2[i] == identity:
            id += 1
        else:
            # differences include all mismatches among '+' and '-', other symbols are ignored
            if (P1[i] == "+" and P2[i] == "-") or (P1[i] == "-" and P2[i] == "+"):
                dif += 1
    return dif / (dif + id) if (dif + id) > 0 else 0.0



# Genera il contenuto di un file.txt in memoria, replicando distance.py
def generate_matrix_txt(languages, rows, dist_func, identity=None):
    output = StringIO()
    lang_data = [[r['cells'][i]['val'] for r in rows] for i in range(len(languages))]
    headers = ["Language"] + [l.id for l in languages]
    output.write("\t".join(headers) + "\n")

    for i, l1 in enumerate(languages):
        row_vals = [l1.id]
        for j, l2 in enumerate(languages):
            if identity is None:
                d = dist_func(lang_data[i], lang_data[j])
            else:
                d = dist_func(lang_data[i], lang_data[j], identity)
            row_vals.append(str(d))
        output.write("\t".join(row_vals) + "\n")
    return output.getvalue()


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
        # Genera i due file .txt richiesti da distance.py
        zf.writestr("hamming.txt", generate_matrix_txt(languages, rows, hamming_core))
        zf.writestr("jaccard[+].txt", generate_matrix_txt(languages, rows, jaccard_core, identity="+"))

    buf.seek(0)
    response = HttpResponse(buf.getvalue(), content_type="application/zip")
    response["Content-Disposition"] = 'attachment; filename="distances_txt.zip"'
    return response

# Crea l'immagine del dendrogramma in memoria usando la logica esatta di dendrogram.py
def create_dendrogram_image(matrix_data, language_labels, title):
    # squareform accetta solo matrici simmetriche perfette
    condensed_matrix = squareform(matrix_data)

    # method="average" come in hc_from_distances
    linkage_matrix = linkage(condensed_matrix, method='average')

    # Impostazioni visive estratte da hc_dendrogram
    plt.figure(figsize=(12, 8))
    dendrogram(
        linkage_matrix,
        labels=language_labels,
        orientation='top',
        distance_sort='descending',
        show_leaf_counts=True,
        color_threshold=0,
        above_threshold_color='black'
    )
    plt.title(title)
    plt.xlabel("Languages")
    plt.ylabel("Distance")
    plt.tight_layout()

    img_buf = BytesIO()
    plt.savefig(img_buf, format='png', dpi=300, bbox_inches="tight")
    plt.close()
    return img_buf.getvalue()

# Ricalcola le matrici e restituisce uno zip con entrambi i dendrogrammi
@login_required
def tablea_export_dendrogram(request):
    languages, rows, _ = get_tablea_filtered_data(request)
    if not languages: return HttpResponse("No data")

    lang_data = [[r['cells'][i]['val'] for r in rows] for i in range(len(languages))]
    labels = [l.id for l in languages]

    # Calcolo matrice Hamming
    matrix_hamming = [[hamming_core(lang_data[i], lang_data[j]) for j in range(len(languages))] for i in
                      range(len(languages))]

    # Calcolo matrice Jaccard[+]
    matrix_jaccard = [[jaccard_core(lang_data[i], lang_data[j], identity="+") for j in range(len(languages))] for i in
                      range(len(languages))]

    # Creazione dello zip in RAM
    zip_buf = BytesIO()
    with zipfile.ZipFile(zip_buf, "w") as zf:
        # Dendrogramma Hamming
        img_hamming = create_dendrogram_image(matrix_hamming, labels, "Dendrogram, hamming, average")
        zf.writestr("dendrogram_hamming_average.png", img_hamming)

        # Dendrogramma Jaccard[+]
        img_jaccard = create_dendrogram_image(matrix_jaccard, labels, "Dendrogram, jaccard[+], average")
        zf.writestr("dendrogram_jaccard[+]_average.png", img_jaccard)

    zip_buf.seek(0)
    response = HttpResponse(zip_buf.getvalue(), content_type="application/zip")
    response["Content-Disposition"] = 'attachment; filename="dendrograms.zip"'
    return response