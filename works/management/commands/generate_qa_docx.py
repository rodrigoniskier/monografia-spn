"""Gera uma monografia preenchida para inspeção visual do exportador."""

from datetime import date
from pathlib import Path

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from works.models import CitationNote, Monograph, Publication, ReferenceEntry, Section
from works.services.docx_export import build_monograph_docx
from works.services.reference_import import reference_checksum


PARAGRAPH = (
    "A pesquisa teológica exige que a interpretação das fontes seja articulada "
    "com uma argumentação clara e responsável. Nesse percurso, a tradição reformada "
    "não é tratada como substituta da Escritura, mas como testemunho histórico que "
    "auxilia a igreja a formular, examinar e comunicar suas convicções. A análise "
    "considera o contexto dos autores, a coerência interna das proposições e as "
    "implicações pastorais decorrentes da tese defendida."
)


class Command(BaseCommand):
    help = "Gera um DOCX de QA com todos os elementos principais da monografia."

    def add_arguments(self, parser):
        parser.add_argument("--output", required=True)

    def handle(self, *args, **options):
        user, _ = User.objects.get_or_create(username="qa_spn", defaults={"first_name": "Autor", "last_name": "de Teste"})
        user.set_unusable_password()
        user.save(update_fields=["password"])
        work, _ = Monograph.objects.get_or_create(owner=user, title="A centralidade de Cristo na proclamação contemporânea")
        values = {
            "author_name": "AUTOR DE TESTE",
            "subtitle": "fundamentos bíblico-teológicos e implicações pastorais",
            "advisor_name": "ORIENTADOR DE TESTE",
            "advisor_title": "Rev. Dr.",
            "year": 2025,
            "approval_date": date(2025, 11, 30),
            "examiner_internal_name": "EXAMINADOR INTERNO DE TESTE",
            "examiner_internal_title": "Rev. Ms.",
            "examiner_internal_institution": "Seminário Presbiteriano do Norte - SPN",
            "examiner_external_name": "EXAMINADOR EXTERNO DE TESTE",
            "examiner_external_title": "Rev. Dr.",
            "examiner_external_institution": "Presbitério de Recife",
            "theme": "Pregação cristocêntrica",
            "delimitation": "A proclamação reformada no contexto urbano brasileiro contemporâneo.",
            "research_problem": "Como a centralidade de Cristo orienta a proclamação cristã no contexto contemporâneo?",
            "general_objective": "Analisar a centralidade de Cristo na proclamação contemporânea.",
            "specific_objectives": "Examinar o contexto histórico.\nSistematizar os fundamentos bíblicos.\nAvaliar implicações pastorais.",
            "justification": PARAGRAPH,
            "methodology": "Pesquisa bibliográfica, qualitativa e de orientação teológico-sistemática.",
            "dedication": "À igreja de Cristo, chamada a anunciar fielmente o evangelho.",
            "acknowledgements": PARAGRAPH + "\n\n" + PARAGRAPH,
            "epigraph_text": "Pregamos a Cristo, poder de Deus e sabedoria de Deus.",
            "epigraph_author": "Paráfrase temática de 1 Coríntios 1",
            "confessional_subtitle": "Da Sagrada Escritura e de Cristo, o Mediador",
            "confessional_content": PARAGRAPH + "\n\n" + PARAGRAPH,
            "confessional_references": "Confissão de Fé de Westminster, capítulos I e VIII.",
            "abstract_pt": "Este trabalho analisa a centralidade de Cristo na proclamação contemporânea. A pesquisa é bibliográfica, qualitativa e orientada pela teologia reformada. O estudo percorre o contexto histórico, os fundamentos bíblico-confessionais e as implicações pastorais do tema. Conclui-se que a proclamação cristocêntrica oferece coerência teológica e direção pastoral para a igreja contemporânea.",
            "keywords_pt": "Cristo; Pregação; Teologia reformada; Igreja.",
            "abstract_en": "This study analyzes the centrality of Christ in contemporary proclamation. It follows a qualitative bibliographical approach informed by Reformed theology and considers historical, biblical-confessional, and pastoral dimensions.",
            "keywords_en": "Christ; Preaching; Reformed theology; Church.",
            "abbreviations": "ABNT — Associação Brasileira de Normas Técnicas\nIPB — Igreja Presbiteriana do Brasil\nSPN — Seminário Presbiteriano do Norte",
            "symbols": "§ — Seção\nα — Alfa",
            "introduction": "\n\n".join([PARAGRAPH] * 5),
            "conclusion": "\n\n".join([PARAGRAPH] * 4),
            "glossary": "Cristocêntrico — Aquilo que tem Cristo como centro.\nProclamação — Comunicação pública da mensagem cristã.",
            "appendices": "APÊNDICE A — ROTEIRO DE ANÁLISE\n\n" + PARAGRAPH,
            "annexes": "ANEXO A — DOCUMENTO CONFESSIONAL\n\n" + PARAGRAPH,
        }
        for key, value in values.items():
            setattr(work, key, value)
        work.save()
        work.sections.all().delete()
        for index, title in enumerate([
            "Contexto histórico e desafios da proclamação",
            "Fundamentos bíblico-teológicos e confessionais",
            "Implicações pastorais para a igreja contemporânea",
        ], start=1):
            section = Section.objects.create(monograph=work, title=title, level=1, order=index, content="\n\n".join([PARAGRAPH] * 6))
            Section.objects.create(monograph=work, parent=section, title=f"Aspectos específicos da seção {index}", level=2, order=1, content="\n\n".join([PARAGRAPH] * 3))
        work.publications.all().delete()
        work.reference_entries.all().delete()
        work.citation_notes.all().delete()
        Publication.objects.create(monograph=work, source_type="book", title="Institutas da religião cristã", authors=["João Calvino"], year=2006, city="São Paulo", publisher="Cultura Cristã", url="https://openlibrary.org/works/OL123W", provider="Open Library")
        Publication.objects.create(monograph=work, source_type="article", title="Christ-centered proclamation", authors=["Maria da Silva", "John Smith"], year=2025, container_title="Journal of Reformed Theology", volume="19", issue="2", pages="100-122", doi="10.1000/example", url="https://doi.org/10.1000/example", provider="Crossref")
        imported_text = "HORTON, Michael. A missão da igreja no mundo contemporâneo. São Paulo: Cultura Cristã, 2012."
        imported = ReferenceEntry.objects.create(
            monograph=work,
            text=imported_text,
            source_filename="referencias-qa.docx",
            checksum=reference_checksum(imported_text),
            order=1,
        )
        note = CitationNote.objects.create(
            monograph=work,
            target_key="monograph:introduction",
            sequence=1,
            reference_text=imported_text + " p. 42.",
            reference_entry=imported,
        )
        insertion = work.introduction.find(".") + 1
        work.introduction = (
            work.introduction[:insertion] + note.token + work.introduction[insertion:]
        )
        work.save(update_fields=["introduction", "updated_at"])
        output_path = Path(options["output"]).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(build_monograph_docx(work).getvalue())
        self.stdout.write(self.style.SUCCESS(f"DOCX de QA gerado em {output_path}"))
