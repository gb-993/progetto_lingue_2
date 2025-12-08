from django.shortcuts import render


def instruction_page(request):
    """
    Pagina Instruction, visibile a tutti (user e admin).
    Contenuto fittizio per ora.
    """
    return render(request, "instructions/instructions.html", {})
