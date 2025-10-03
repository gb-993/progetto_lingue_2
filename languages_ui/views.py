from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Prefetch
from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from django.views.decorators.http import require_http_methods
from django.utils.translation import gettext as _
from types import SimpleNamespace
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from core.models import (
    Language, ParameterDef, Question, Answer, Example, Motivation, AnswerMotivation, QuestionAllowedMotivation
)
from .forms import LanguageForm


@login_required
def language_list(request):
    q = (request.GET.get("q") or "").strip()
    user = request.user
    is_admin = (getattr(user, "role", "") == "admin") or user.is_staff or user.is_superuser

    qs = Language.objects.select_related("assigned_user").order_by("position")

    # 🔒 Filtro di sicurezza: gli user vedono solo le lingue a loro attribuite
    if not is_admin:
        qs = qs.filter(
            Q(assigned_user=user) | Q(users=user)  # FK assigned_user OPPURE M2M user.m2m_languages
        )

    # Ricerca
    if q:
        search_filter = (
            Q(id__icontains=q) |
            Q(name_full__icontains=q) |
            Q(isocode__icontains=q) |
            Q(glottocode__icontains=q) |
            Q(grp__icontains=q) |
            Q(informant__icontains=q) |
            Q(supervisor__icontains=q)
        )
        # Consenti di cercare per email assegnata solo agli admin (per privacy)
        if is_admin:
            search_filter |= Q(assigned_user__email__icontains=q)

        qs = qs.filter(search_filter)

    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get("page"))
    ctx = {
        "languages": page_obj.object_list,
        "page_obj": page_obj,
        "q": q,
        "is_admin": is_admin,   # ➜ usato dal template per i bottoni
    }
    return render(request, "languages/list.html", ctx)



@login_required
@require_http_methods(["GET", "POST"])
def language_add(request):
    if request.method == "POST":
        form = LanguageForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, _("Language created."))
            return redirect("language_list")
    else:
        form = LanguageForm()
    return render(request, "languages/add.html", {"page_title": "Add language", "form": form})


@login_required
@require_http_methods(["GET", "POST"])
def language_edit(request, lang_id):
    lang = get_object_or_404(Language, pk=lang_id)
    if request.method == "POST":
        form = LanguageForm(request.POST, instance=lang)
        if form.is_valid():
            form.save()
            messages.success(request, _("Language updated."))
            return redirect("language_list")
    else:
        form = LanguageForm(instance=lang)
    return render(request, "languages/edit.html", {"page_title": "Edit language", "form": form, "language": lang})


@login_required
def language_data(request, lang_id):
    user = request.user
    is_admin = (getattr(user, "role", "") == "admin") or user.is_staff or user.is_superuser

    lang = get_object_or_404(Language, pk=lang_id)

    # 🔒 Access control: admin OK; altrimenti solo se assegnata via FK o M2M
    if not is_admin:
        if not (
            (lang.assigned_user_id == user.id) or
            lang.users.filter(pk=user.pk).exists()
        ):
            messages.error(request, _("You don't have access to this language."))
            return redirect("language_list")

    # ✅ Correzione prefetch: usa la reverse della tabella ponte
    #    - "allowed_motivation_links" è il related_name sulla FK question
    #    - queryset = QuestionAllowedMotivation (select_related('motivation'))
    #    - to_attr="allowed_motivs_through" per avere a disposizione la lista dei link (ordinati)
    parameters = (
        ParameterDef.objects.filter(is_active=True)
        .order_by("position")
        .prefetch_related(
            Prefetch(
                "questions",
                queryset=(
                    Question.objects.order_by("id")
                    .prefetch_related(
                        Prefetch(
                            "allowed_motivation_links",
                            queryset=QuestionAllowedMotivation.objects
                                .select_related("motivation")
                                .order_by("position", "id"),
                            to_attr="allowed_motivs_through",
                        )
                    )
                ),
            )
        )
    )

    # Risposte già presenti
    answers_qs = (
        Answer.objects.filter(language=lang)
        .select_related("question")
        .prefetch_related("answer_motivations__motivation", "examples")
    )
    by_qid = {a.question_id: a for a in answers_qs}

    from types import SimpleNamespace
    for p in parameters:
        total = 0
        answered = 0
        for q in p.questions.all():
            total += 1

            # 👉 Lista motivazioni ammesse PER QUESTA DOMANDA (estratte dalla ponte)
            #    q.allowed_motivs_through è popolato dal Prefetch sopra
            q.allowed_motivations_list = [thr.motivation for thr in getattr(q, "allowed_motivs_through", [])]

            a = by_qid.get(q.id)
            if a:
                ans_ns = SimpleNamespace(
                    response_text=a.response_text,
                    comments=a.comments or "",
                    motivation_ids=[am.motivation_id for am in a.answer_motivations.all()],
                    examples=list(a.examples.all()),
                    answer_id=a.id,
                )
                if a.response_text in ("yes", "no"):
                    answered += 1
            else:
                ans_ns = SimpleNamespace(
                    response_text="yes",  # default
                    comments="",
                    motivation_ids=[],
                    examples=[],
                    answer_id=None,
                )
            q.ans = ans_ns

        if total == 0:
            p.status = "ok"
        elif answered == 0:
            p.status = "missing"
        elif answered < total:
            p.status = "warn"
        else:
            p.status = "ok"

    ctx = {"language": lang, "parameters": parameters}
    return render(request, "languages/data.html", ctx)




@login_required
@require_http_methods(["POST"])
def answer_save(request, lang_id, question_id):
    """
    Salva Answer (yes/no), comments e motivazioni multiple.
    - Mostriamo motivazioni solo se NO (client-side).
    - Qui VALIDiamo lato server: le motivazioni inviate DEVONO essere tra le allowed per la domanda.
    - Regola esclusiva: se è presente 'Motivazione1', scartiamo tutte le altre.
    """
    lang = get_object_or_404(Language, pk=lang_id)
    question = get_object_or_404(Question, pk=question_id)

    response_text = (request.POST.get("response_text") or "").strip().lower()
    if response_text not in ("yes", "no"):
        messages.error(request, _("Invalid answer value."))
        return redirect("language_data", lang_id=lang.id)

    comments = (request.POST.get("comments") or "").strip()

    # Motivazioni inviate (da <select multiple name="motivation_ids">)
    try:
        motivation_ids = [int(x) for x in request.POST.getlist("motivation_ids")]
    except ValueError:
        motivation_ids = []

    # Calcola l'insieme degli ID ammessi per questa domanda
    allowed_ids = set(
        QuestionAllowedMotivation.objects.filter(question=question)
        .values_list("motivation_id", flat=True)
    )

    # Se YES, nessuna motivazione è ammessa
    if response_text == "yes":
        motivation_ids = []
    else:
        # Filtro al sottoinsieme ammesso
        motivation_ids = [mid for mid in motivation_ids if mid in allowed_ids]

        # Regola esclusiva: 'Motivazione1' disabilita le altre (se esiste tra le allowed)
        # NB: usiamo la label perché non abbiamo un flag dedicato a DB
        mot1 = Motivation.objects.filter(label="Motivazione1").first()
        if mot1 and mot1.id in motivation_ids:
            motivation_ids = [mot1.id]  # tieni solo lei

    # Upsert Answer
    answer, _created = Answer.objects.get_or_create(
        language=lang,
        question=question,
        defaults={"response_text": response_text, "comments": comments},
    )
    answer.response_text = response_text
    answer.comments = comments
    answer.save()

    # Sync motivazioni (solo quelle validate)
    current_ids = set(AnswerMotivation.objects.filter(answer=answer).values_list("motivation_id", flat=True))
    target_ids = set(motivation_ids)

    to_add = target_ids - current_ids
    to_del = current_ids - target_ids

    if to_add:
        rows = [AnswerMotivation(answer=answer, motivation_id=mid) for mid in to_add]
        AnswerMotivation.objects.bulk_create(rows, ignore_conflicts=True)
    if to_del:
        AnswerMotivation.objects.filter(answer=answer, motivation_id__in=to_del).delete()

    # Aggiorno Examples esistenti (pattern: ex_<id>_<field>)
    for key, val in request.POST.items():
        if not key.startswith("ex_"):
            continue
        try:
            _ex, ex_id, field = key.split("_", 2)
            ex_id = int(ex_id)
        except ValueError:
            continue
        if field not in {"textarea", "transliteration", "gloss", "translation", "reference"}:
            continue
        Example.objects.filter(id=ex_id, answer=answer).update(**{field: val})

    messages.success(request, _("Answer saved."))
    return redirect("language_data", lang_id=lang.id)



# Placeholder per compatibilità con i template
@login_required
def language_export(request, lang_id):
    lang = get_object_or_404(Language, pk=lang_id)
    messages.info(request, _("Export is not implemented yet."))
    return redirect("language_data", lang_id=lang.id)

@login_required
def language_debug(request, lang_id):
    lang = get_object_or_404(Language, pk=lang_id)
    messages.info(request, _("Debug page is not implemented yet."))
    return redirect("language_data", lang_id=lang.id)

@login_required
def language_save_instructions(request, lang_id):
    messages.info(request, _("Instructions are not supported yet (no model to store them)."))
    return redirect("language_data", lang_id=lang_id)

@login_required
def language_approve(request, lang_id):
    messages.info(request, _("Approval flow not implemented yet."))
    return redirect("language_data", lang_id=lang_id)

@login_required
def language_reopen(request, lang_id):
    messages.info(request, _("Reopen flow not implemented yet."))
    return redirect("language_data", lang_id=lang_id)


# languages_ui/views.py
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from django.db.models import Prefetch

from core.models import (
    Language, ParameterDef, Question, Answer,
    LanguageParameter,  # valore consolidato da risposte (+/-/0 o None)
)

# Se hai il modello con i valori del DAG, importalo.
# Se NON esiste nel tuo progetto, lascia il try/except: la colonna finale rimarrà vuota.
try:
    from core.models import LanguageParameterEval  # valore DAG (+/-/0 o None)
    HAS_EVAL = True
except Exception:
    LanguageParameterEval = None
    HAS_EVAL = False

# languages_ui/views.py
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from django.db.models import Prefetch

from core.models import (
    Language, ParameterDef, Question, Answer,
    LanguageParameter, LanguageParameterEval,  # usiamo entrambi
)

@login_required
def language_debug(request, lang_id: str):
    """
    Debug per una lingua:
      - per ogni parametro attivo in ordine di position
      - mostra: domande (ID), risposte (yes/no), initial value (+/-), final value (+/-/0)
    """
    user = request.user
    is_admin = (getattr(user, "role", "") == "admin") or user.is_staff or user.is_superuser

    # lingua e controllo accessi (admin ok; altrimenti assegnata via M2M o FK)
    lang = get_object_or_404(Language, pk=lang_id)
    if not is_admin:
        allowed = False
        # M2M: language.users
        try:
            allowed = lang.users.filter(pk=user.pk).exists()
        except Exception:
            allowed = False
        # FK fallback: assigned_user
        if not allowed:
            allowed = (getattr(lang, "assigned_user_id", None) == user.id)
        if not allowed:
            # 404 per non rivelare info
            get_object_or_404(Language, pk="__deny__")

    # Parametri attivi (ordine di sito) + domande prefetchate
    params = (
        ParameterDef.objects
        .filter(is_active=True)
        .order_by("position", "id")
        .prefetch_related(Prefetch("questions", queryset=Question.objects.order_by("id")))
    )

    # Tutte le risposte della lingua, indicizzate per question_id
    answers = (
        Answer.objects
        .filter(language=lang)
        .select_related("question")
        .order_by("question__parameter__position", "question_id")
    )
    answers_by_qid = {a.question_id: a for a in answers}

    # Initial & Final values + warnings
    lps = (
        LanguageParameter.objects
        .filter(language=lang)
        .select_related("parameter", "eval")
    )

    init_by_pid   = {}
    warni_by_pid  = {}  # warning iniziale (warning_orig)
    final_by_pid  = {}
    warnf_by_pid  = {}  # warning finale (warning_eval)

    for lp in lps:
        pid = lp.parameter_id
        init_by_pid[pid]  = (lp.value_orig or "")
        warni_by_pid[pid] = bool(lp.warning_orig)
        if getattr(lp, "eval", None):
            final_by_pid[pid] = (lp.eval.value_eval or "")
            warnf_by_pid[pid] = bool(lp.eval.warning_eval)
        else:
            final_by_pid[pid] = ""
            warnf_by_pid[pid] = False

    # Prepara righe per template (aggiungiamo i due flag)
    rows = []
    for p in params:
        q_ids, q_ans = [], []
        for q in p.questions.all():
            q_ids.append(q.id)
            a = answers_by_qid.get(q.id)
            q_ans.append((a.response_text.upper() if (a and a.response_text in ("yes", "no")) else ""))

        rows.append({
            "position": p.position,
            "param_id": p.id,
            "name": p.name or "",
            "questions": q_ids,
            "answers": q_ans,
            "initial":  (init_by_pid.get(p.id, "") or ""),
            "final":    (final_by_pid.get(p.id, "") or ""),
            "warn_init": bool(warni_by_pid.get(p.id, False)),  
            "warn_final": bool(warnf_by_pid.get(p.id, False)), 
            "cond": (p.implicational_condition or ""),
        })


    ctx = {"language": lang, "rows": rows}
    return render(request, "languages/debug_parameters.html", ctx)



from django.views.decorators.http import require_POST
from django.contrib import messages
from django.utils.translation import gettext as _
# importa il servizio del DAG
from core.services.dag_eval import run_dag_for_language

@login_required
@require_POST
def language_run_dag(request, lang_id: str):
    """
    Esegue il DAG per la lingua e torna alla pagina di debug.
    Consentito solo admin (o staff/superuser).
    """
    user = request.user
    is_admin = (getattr(user, "role", "") == "admin") or user.is_staff or user.is_superuser

    if not is_admin:
        messages.error(request, _("You are not allowed to run the DAG."))
        return redirect("language_debug", lang_id=lang_id)

    # (opzionale) qui potresti fare anche un controllo di accesso aggiuntivo sulla lingua
    # ma visto che è azione admin ha senso lasciarlo così.

    try:
        report = run_dag_for_language(lang_id)
        # Messaggio riassuntivo amichevole
        msg = _(
            "DAG completed: processed %(p)d, forced to zero %(fz)d, missing orig %(mo)d, warnings propagated %(wp)d."
        ) % {
            "p": len(report.processed or []),
            "fz": len(report.forced_zero or []),
            "mo": len(report.missing_orig or []),
            "wp": len(report.warnings_propagated or []),
        }
        # Se vuoi vedere elenco dettagli in debug:
        if report.missing_orig:
            msg += " Missing: " + ", ".join(report.missing_orig[:8]) + ("…" if len(report.missing_orig) > 8 else "")
        messages.success(request, msg)
    except Exception as e:
        messages.error(request, _("DAG failed: %(err)s") % {"err": str(e)})
    return redirect("language_debug", lang_id=lang_id)
