from __future__ import annotations

from datetime import date
import re
import uuid

from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    full_name = models.CharField(max_length=180)
    onboarding_seen = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.full_name or self.user.username


class Monograph(models.Model):
    STATUS_CHOICES = [
        ("draft", "Em elaboração"),
        ("review", "Em revisão"),
        ("finished", "Concluída"),
    ]

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="monographs")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="draft")

    # Identificação institucional, baseada no padrão recorrente dos trabalhos do SPN.
    author_name = models.CharField(max_length=180, blank=True)
    institution_line_1 = models.CharField(
        max_length=180, default="IGREJA PRESBITERIANA DO BRASIL - IPB"
    )
    institution_line_2 = models.CharField(
        max_length=180, default="JUNTA DE EDUCAÇÃO TEOLÓGICA - JET"
    )
    institution_line_3 = models.CharField(
        max_length=180,
        default="JUNTA REGIONAL DE EDUCAÇÃO TEOLÓGICA - JURET/RECIFE",
    )
    institution_line_4 = models.CharField(
        max_length=180, default="SEMINÁRIO PRESBITERIANO DO NORTE - SPN"
    )
    course_name = models.CharField(
        max_length=180, default="CURSO LIVRE DE BACHARELADO EM TEOLOGIA"
    )
    city = models.CharField(max_length=100, default="Recife - PE")
    year = models.PositiveSmallIntegerField(
        default=date.today().year,
        validators=[MinValueValidator(1900), MaxValueValidator(2200)],
    )
    advisor_name = models.CharField(max_length=180, blank=True)
    advisor_title = models.CharField(max_length=80, blank=True, default="Rev.")
    nature_text = models.TextField(
        default=(
            "Monografia apresentada ao Seminário Presbiteriano do Norte - SPN, "
            "em cumprimento às exigências para a conclusão do Curso Livre de "
            "Bacharelado em Teologia."
        )
    )

    # Planejamento da pesquisa.
    title = models.CharField(max_length=300, blank=True)
    subtitle = models.CharField(max_length=300, blank=True)
    theme = models.TextField(blank=True)
    delimitation = models.TextField(blank=True)
    research_problem = models.TextField(blank=True)
    hypothesis = models.TextField(blank=True)
    general_objective = models.TextField(blank=True)
    specific_objectives = models.TextField(blank=True)
    justification = models.TextField(blank=True)
    methodology = models.TextField(blank=True)
    planning_keywords = models.CharField(max_length=500, blank=True)

    # Folha de aprovação.
    approval_date = models.DateField(null=True, blank=True)
    examiner_internal_name = models.CharField(max_length=180, blank=True)
    examiner_internal_title = models.CharField(max_length=80, blank=True, default="Rev.")
    examiner_internal_institution = models.CharField(
        max_length=180, blank=True, default="Seminário Presbiteriano do Norte - SPN"
    )
    examiner_external_name = models.CharField(max_length=180, blank=True)
    examiner_external_title = models.CharField(max_length=80, blank=True, default="Rev.")
    examiner_external_institution = models.CharField(max_length=180, blank=True)

    # Elementos pré-textuais e marca institucional/confessional.
    dedication = models.TextField(blank=True)
    acknowledgements = models.TextField(blank=True)
    epigraph_text = models.TextField(blank=True)
    epigraph_author = models.CharField(max_length=180, blank=True)
    confessional_title = models.CharField(
        max_length=300, blank=True, default="CONFISSÃO DE FÉ DE WESTMINSTER"
    )
    confessional_subtitle = models.CharField(max_length=300, blank=True)
    confessional_content = models.TextField(blank=True)
    confessional_references = models.TextField(blank=True)
    abstract_pt = models.TextField(blank=True)
    keywords_pt = models.CharField(max_length=500, blank=True)
    abstract_en = models.TextField(blank=True)
    keywords_en = models.CharField(max_length=500, blank=True)
    abbreviations = models.TextField(blank=True)
    symbols = models.TextField(blank=True)

    # Elementos textuais e pós-textuais.
    introduction = models.TextField(blank=True)
    conclusion = models.TextField(blank=True)
    glossary = models.TextField(blank=True)
    appendices = models.TextField(blank=True)
    annexes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.title or f"Monografia de {self.author_name or self.owner.username}"

    @property
    def display_title(self):
        return self.title or "Monografia sem título"

    @property
    def completion_percentage(self):
        required = [
            self.author_name,
            self.title,
            self.theme,
            self.delimitation,
            self.research_problem,
            self.general_objective,
            self.specific_objectives,
            self.justification,
            self.methodology,
            self.abstract_pt,
            self.keywords_pt,
            self.introduction,
            self.conclusion,
        ]
        section_total = self.sections.filter(level=1).count()
        section_ready = self.sections.filter(level=1).exclude(content="").count()
        done = sum(bool(str(value).strip()) for value in required) + section_ready
        total = len(required) + max(section_total, 1)
        return round(done * 100 / total)

    @property
    def research_query(self):
        values = [self.theme, self.delimitation, self.planning_keywords]
        query = " ".join(value.strip() for value in values if value and value.strip())
        return re.sub(r"\s+", " ", query)[:500]


class Section(models.Model):
    monograph = models.ForeignKey(
        Monograph, on_delete=models.CASCADE, related_name="sections"
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        related_name="children",
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=300)
    content = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    level = models.PositiveSmallIntegerField(
        default=1, validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    guidance_key = models.CharField(max_length=60, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.title

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.parent and self.parent.monograph_id != self.monograph_id:
            raise ValidationError("A subseção deve pertencer à mesma monografia.")
        expected_level = (self.parent.level + 1) if self.parent else 1
        if self.level != expected_level:
            self.level = expected_level


class Publication(models.Model):
    SOURCE_TYPES = [
        ("book", "Livro"),
        ("article", "Artigo"),
        ("chapter", "Capítulo de livro"),
        ("thesis", "Tese ou dissertação"),
        ("other", "Outro"),
    ]

    monograph = models.ForeignKey(
        Monograph, on_delete=models.CASCADE, related_name="publications"
    )
    source_type = models.CharField(max_length=16, choices=SOURCE_TYPES, default="other")
    title = models.CharField(max_length=500)
    subtitle = models.CharField(max_length=500, blank=True)
    authors = models.JSONField(default=list, blank=True)
    year = models.PositiveSmallIntegerField(null=True, blank=True)
    city = models.CharField(max_length=150, blank=True)
    publisher = models.CharField(max_length=250, blank=True)
    edition = models.CharField(max_length=80, blank=True)
    container_title = models.CharField(max_length=500, blank=True)
    volume = models.CharField(max_length=50, blank=True)
    issue = models.CharField(max_length=50, blank=True)
    pages = models.CharField(max_length=80, blank=True)
    doi = models.CharField(max_length=200, blank=True)
    isbn = models.CharField(max_length=80, blank=True)
    url = models.URLField(max_length=1000)
    language = models.CharField(max_length=30, blank=True)
    provider = models.CharField(max_length=60)
    verified_at = models.DateTimeField(default=timezone.now)
    access_date = models.DateField(default=date.today)
    notes = models.TextField(blank=True)
    raw_metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["title", "year"]
        constraints = [
            models.UniqueConstraint(
                fields=["monograph", "url"], name="unique_publication_url_per_monograph"
            )
        ]

    def __str__(self):
        return self.title


class ReferenceEntry(models.Model):
    """Referência ABNT importada pelo autor a partir de DOCX ou PDF."""

    monograph = models.ForeignKey(
        Monograph, on_delete=models.CASCADE, related_name="reference_entries"
    )
    text = models.TextField(max_length=4000)
    source_filename = models.CharField(max_length=255, blank=True)
    checksum = models.CharField(max_length=64)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["monograph", "checksum"],
                name="unique_imported_reference_per_monograph",
            )
        ]

    def __str__(self):
        return self.text[:120]


class CitationNote(models.Model):
    """Nota referencial vinculada a um marcador estável dentro do texto."""

    monograph = models.ForeignKey(
        Monograph, on_delete=models.CASCADE, related_name="citation_notes"
    )
    marker = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    target_key = models.CharField(max_length=120)
    sequence = models.PositiveIntegerField()
    reference_text = models.TextField(max_length=4000)
    reference_entry = models.ForeignKey(
        ReferenceEntry,
        on_delete=models.SET_NULL,
        related_name="citation_notes",
        null=True,
        blank=True,
    )
    publication = models.ForeignKey(
        Publication,
        on_delete=models.SET_NULL,
        related_name="citation_notes",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sequence", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["monograph", "sequence"],
                name="unique_citation_sequence_per_monograph",
            )
        ]

    @property
    def token(self):
        return f"[[FN:{self.marker}]]"

    def __str__(self):
        return f"Nota {self.sequence} — {self.reference_text[:100]}"


class AIRevision(models.Model):
    ACTIONS = [
        ("review", "Análise acadêmica"),
        ("polish", "Aprimoramento de redação"),
        ("outline", "Sugestão de estrutura"),
        ("translate", "Tradução acadêmica"),
    ]

    monograph = models.ForeignKey(
        Monograph, on_delete=models.CASCADE, related_name="ai_revisions"
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="ai_revisions")
    target_key = models.CharField(max_length=120)
    action = models.CharField(max_length=20, choices=ACTIONS)
    original_text = models.TextField(blank=True)
    proposed_text = models.TextField(blank=True)
    suggestions = models.JSONField(default=list, blank=True)
    warnings = models.JSONField(default=list, blank=True)
    model_name = models.CharField(max_length=80, blank=True)
    accepted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_action_display()} - {self.target_key}"
