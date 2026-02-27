from django.shortcuts import redirect
from django.urls import reverse


class TermsAcceptanceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and not request.user.terms_accepted:
            # Consenti all'utente di visitare solo la pagina di accettazione o di fare logout
            allowed_paths = [reverse('accept_terms'), reverse('logout')]

            # Escludiamo file statici e percorsi consentiti
            if request.path not in allowed_paths and not request.path.startswith('/static/'):
                # Lo reindirizziamo alla finestra di accettazione
                url = f"{reverse('accept_terms')}?next={request.path}"
                return redirect(url)

        return self.get_response(request)