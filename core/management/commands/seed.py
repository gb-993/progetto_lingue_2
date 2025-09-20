from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import User, Motivation, ParameterDef, Language, Question


class Command(BaseCommand):
    help = "Popola il database con dati iniziali (utenti, motivazioni, parametri demo, lingue)"

    def handle(self, *args, **options):
        # === Utenti ===
        if not User.objects.filter(email="admin@example.com").exists():
            User.objects.create_superuser(
                email="admin@example.com",
                password="admin123",
                name="Admin",
                surname="User",
            )
            self.stdout.write(self.style.SUCCESS("Creato superuser admin@example.com / admin123"))

        if not User.objects.filter(email="user@example.com").exists():
            User.objects.create_user(
                email="user@example.com",
                password="user123",
                name="Mario",
                surname="Rossi",
                role="user",
            )
            self.stdout.write(self.style.SUCCESS("Creato utente user@example.com / user123"))

        # === Motivazioni ===
        mot_data = [
            ("MOT1", "Motivazione 1"),
            ("MOT2", "Motivazione linguistica"),
            ("MOT3", "Motivazione sociolinguistica"),
        ]
        for code, label in mot_data:
            Motivation.objects.get_or_create(code=code, defaults={"label": label})


        # === Parametri demo ===
        if not ParameterDef.objects.filter(id="FGM").exists():
            ParameterDef.objects.create(
                id="FGM",
                name="Feature Gender Marker",
                short_description="Parametro demo",
                position=1,
                is_active=True,
            )
        if not ParameterDef.objects.filter(id="FGK").exists():
            ParameterDef.objects.create(
                id="FGK",
                name="Feature Gender Knowledge",
                short_description="Altro parametro demo",
                position=2,
                is_active=True,
            )
        self.stdout.write(self.style.SUCCESS("Parametri demo creati"))

        # === Lingua demo ===
        lang, _ = Language.objects.get_or_create(
            id="ita",
            defaults={
                "name_full": "Italiano",
                "position": 1,
                "informant": "Informant Demo",
                "supervisor": "Supervisor Demo",
            },
        )
        self.stdout.write(self.style.SUCCESS(f"Lingua demo creata: {lang.id}"))

        # === Domande demo ===
        Question.objects.get_or_create(
            id="FGMQ_a",
            parameter_id="FGM",
            defaults={"text": "Domanda di esempio per FGM"},
        )
        Question.objects.get_or_create(
            id="FGKQ_a",
            parameter_id="FGK",
            defaults={"text": "Domanda di esempio per FGK"},
        )
        self.stdout.write(self.style.SUCCESS("Domande demo create"))

        self.stdout.write(self.style.SUCCESS("Seed completato!"))
