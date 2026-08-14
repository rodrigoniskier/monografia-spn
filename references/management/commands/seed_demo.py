from datetime import date

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from references.models import Project, ProjectReference, Reference
from references.services.people import parse_people


class Command(BaseCommand):
    help = "Cria uma conta e um projeto demonstrativos para testes locais."

    def add_arguments(self, parser):
        parser.add_argument("--username", default="demo")
        parser.add_argument("--password", required=True)
        parser.add_argument("--email", default="demo@example.com")

    def handle(self, *args, **options):
        if len(options["password"]) < 10:
            raise CommandError(
                "Use uma senha de demonstração com pelo menos 10 caracteres."
            )
        User = get_user_model()
        user, _ = User.objects.get_or_create(
            username=options["username"],
            defaults={
                "email": options["email"],
                "first_name": "Pesquisador",
                "last_name": "Demo",
            },
        )
        user.set_password(options["password"])
        user.save()
        project, _ = Project.objects.get_or_create(
            owner=user,
            name="Revisão sobre inovação em saúde",
            defaults={
                "description": "Projeto demonstrativo do fluxo de referências.",
                "default_style": "abnt",
            },
        )
        samples = [
            {
                "reference_type": Reference.Type.JOURNAL_ARTICLE,
                "authors": parse_people(
                    "Greenhalgh, Trisha; Wherton, Joseph; Papoutsi, Chrysanthi"
                ),
                "title": "Beyond adoption",
                "subtitle": "a new framework for theorizing and evaluating nonadoption, abandonment, and challenges to the scale-up, spread, and sustainability of health and care technologies",
                "year": "2017",
                "container_title": "Journal of Medical Internet Research",
                "volume": "19",
                "issue": "11",
                "pages": "e367",
                "doi": "10.2196/jmir.8775",
            },
            {
                "reference_type": Reference.Type.BOOK,
                "authors": parse_people("Rogers, Everett M."),
                "title": "Diffusion of innovations",
                "year": "2003",
                "edition": "5",
                "publisher_place": "New York",
                "publisher": "Free Press",
            },
            {
                "reference_type": Reference.Type.WEBSITE,
                "authors": parse_people("Instituição: Organização Mundial da Saúde"),
                "title": "Global strategy on digital health 2020–2025",
                "year": "2021",
                "publisher": "World Health Organization",
                "url": "https://www.who.int/publications/i/item/9789240020924",
                "access_date": date.today(),
            },
        ]
        for position, data in enumerate(samples, start=1):
            fingerprint = Reference.make_fingerprint(
                data["title"], data.get("year", ""), data.get("doi", "")
            )
            reference, _ = Reference.objects.get_or_create(
                owner=user,
                normalized_fingerprint=fingerprint,
                defaults={
                    **data,
                    "source_kind": Reference.SourceKind.MANUAL,
                    "extraction_status": Reference.ExtractionStatus.REVIEWED,
                },
            )
            ProjectReference.objects.get_or_create(
                project=project, reference=reference, defaults={"position": position}
            )
        self.stdout.write(
            self.style.SUCCESS(f"Demonstração pronta: usuário={user.username}")
        )
