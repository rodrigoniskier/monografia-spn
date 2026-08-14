import hashlib
import re
import uuid
from pathlib import Path

from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models
from django.urls import reverse

CITATION_STYLES = [
    ("abnt", "ABNT (NBR 6023)"),
    ("apa", "APA 7ª edição"),
    ("vancouver", "Vancouver"),
    ("chicago", "Chicago autor-data"),
    ("harvard", "Harvard"),
    ("ieee", "IEEE"),
]


def reference_upload_path(instance, filename):
    suffix = Path(filename).suffix.lower()
    return f"referencias/{instance.owner_id}/{uuid.uuid4().hex}{suffix}"


class Project(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reference_projects",
    )
    name = models.CharField("nome", max_length=180)
    description = models.TextField("descrição", blank=True)
    default_style = models.CharField(
        "estilo padrão", max_length=20, choices=CITATION_STYLES, default="abnt"
    )
    created_at = models.DateTimeField("criado em", auto_now_add=True)
    updated_at = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "projeto"
        verbose_name_plural = "projetos"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("references:project_detail", kwargs={"pk": self.pk})


class Reference(models.Model):
    class Type(models.TextChoices):
        JOURNAL_ARTICLE = "journal_article", "Artigo de periódico"
        BOOK = "book", "Livro"
        BOOK_CHAPTER = "book_chapter", "Capítulo de livro"
        WEBSITE = "website", "Página da internet"
        THESIS = "thesis", "Dissertação ou tese"
        CONFERENCE = "conference", "Trabalho em evento"
        REPORT = "report", "Relatório"
        OTHER = "other", "Outro"

    class SourceKind(models.TextChoices):
        MANUAL = "manual", "Cadastro manual"
        PDF = "pdf", "Arquivo PDF"
        DOCX = "docx", "Arquivo DOCX"
        PPTX = "pptx", "Arquivo PPTX"
        URL = "url", "URL"

    class ExtractionStatus(models.TextChoices):
        REVIEW = "review", "Revisão necessária"
        REVIEWED = "reviewed", "Revisada"
        FAILED = "failed", "Falha na extração"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="references"
    )
    reference_type = models.CharField(
        "tipo", max_length=30, choices=Type.choices, default=Type.JOURNAL_ARTICLE
    )
    authors = models.JSONField("autores", default=list, blank=True)
    editors = models.JSONField("editores", default=list, blank=True)
    title = models.CharField("título", max_length=600)
    subtitle = models.CharField("subtítulo", max_length=600, blank=True)
    year = models.CharField("ano", max_length=20, blank=True)
    container_title = models.CharField(
        "periódico, livro ou evento", max_length=500, blank=True
    )
    publisher = models.CharField("editora ou instituição", max_length=300, blank=True)
    publisher_place = models.CharField(
        "local de publicação", max_length=180, blank=True
    )
    edition = models.CharField("edição", max_length=50, blank=True)
    volume = models.CharField("volume", max_length=50, blank=True)
    issue = models.CharField("número", max_length=50, blank=True)
    pages = models.CharField("páginas", max_length=80, blank=True)
    doi = models.CharField("DOI", max_length=300, blank=True)
    url = models.URLField("URL", max_length=1000, blank=True)
    access_date = models.DateField("data de acesso", null=True, blank=True)
    language = models.CharField("idioma", max_length=30, blank=True, default="pt")
    notes = models.TextField("observações", blank=True)

    source_kind = models.CharField(
        "origem", max_length=20, choices=SourceKind.choices, default=SourceKind.MANUAL
    )
    source_file = models.FileField(
        "arquivo original",
        upload_to=reference_upload_path,
        blank=True,
        validators=[FileExtensionValidator(["pdf", "docx", "pptx"])],
    )
    original_filename = models.CharField("nome original", max_length=255, blank=True)
    source_url = models.URLField("URL de origem", max_length=1000, blank=True)
    extraction_status = models.CharField(
        "status da extração",
        max_length=20,
        choices=ExtractionStatus.choices,
        default=ExtractionStatus.REVIEW,
    )
    extraction_warnings = models.JSONField(
        "avisos da extração", default=list, blank=True
    )
    normalized_fingerprint = models.CharField(max_length=64, blank=True, db_index=True)
    created_at = models.DateTimeField("criada em", auto_now_add=True)
    updated_at = models.DateTimeField("atualizada em", auto_now=True)

    projects = models.ManyToManyField(
        Project, through="ProjectReference", related_name="references"
    )

    class Meta:
        ordering = ["title"]
        verbose_name = "referência"
        verbose_name_plural = "referências"
        indexes = [
            models.Index(fields=["owner", "doi"]),
            models.Index(fields=["owner", "updated_at"]),
        ]

    def __str__(self):
        return self.title

    @property
    def full_title(self):
        return f"{self.title}: {self.subtitle}" if self.subtitle else self.title

    @property
    def authors_text(self):
        return "\n".join(
            ", ".join(filter(None, [person.get("family", ""), person.get("given", "")]))
            for person in (self.authors or [])
        )

    @staticmethod
    def make_fingerprint(title, year="", doi=""):
        doi_value = (
            re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi or "", flags=re.I)
            .strip()
            .lower()
        )
        normalized_title = re.sub(r"\W+", "", (title or "").casefold())
        payload = f"{doi_value}|{normalized_title}|{year or ''}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def save(self, *args, **kwargs):
        self.doi = re.sub(
            r"^https?://(?:dx\.)?doi\.org/", "", self.doi or "", flags=re.I
        ).strip()
        self.normalized_fingerprint = self.make_fingerprint(
            self.title, self.year, self.doi
        )
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("references:reference_edit", kwargs={"pk": self.pk})


class ProjectReference(models.Model):
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="project_references"
    )
    reference = models.ForeignKey(
        Reference, on_delete=models.CASCADE, related_name="project_links"
    )
    included = models.BooleanField("incluir na lista", default=True)
    position = models.PositiveIntegerField("posição", default=0)
    added_at = models.DateTimeField("adicionada em", auto_now_add=True)

    class Meta:
        ordering = ["position", "added_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "reference"], name="unique_reference_per_project"
            )
        ]
        verbose_name = "referência do projeto"
        verbose_name_plural = "referências do projeto"

    def clean(self):
        from django.core.exceptions import ValidationError

        if (
            self.project_id
            and self.reference_id
            and self.project.owner_id != self.reference.owner_id
        ):
            raise ValidationError(
                "O projeto e a referência devem pertencer ao mesmo usuário."
            )

    def __str__(self):
        return f"{self.project} — {self.reference}"
