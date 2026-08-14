from zipfile import BadZipFile, ZipFile

from django import forms
from django.conf import settings
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Project, Reference
from .services.people import parse_people, people_to_input


class RegistrationForm(UserCreationForm):
    email = forms.EmailField(label="E-mail", required=True)
    first_name = forms.CharField(label="Nome", max_length=150, required=True)
    last_name = forms.CharField(label="Sobrenome", max_length=150, required=False)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = (
            "first_name",
            "last_name",
            "email",
            "username",
            "password1",
            "password2",
        )

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Já existe uma conta com este e-mail.")
        return email


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ("name", "description", "default_style")
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}


class ReferenceForm(forms.ModelForm):
    authors_input = forms.CharField(
        label="Autores",
        required=False,
        widget=forms.Textarea(
            attrs={"rows": 5, "placeholder": "Silva, João\nSouza, Maria Clara"}
        ),
        help_text="Informe um autor por linha, preferencialmente como “Sobrenome, Prenomes”. Para autor institucional, use “Instituição: nome”.",
    )
    editors_input = forms.CharField(
        label="Organizadores ou editores",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Um por linha. Campo especialmente útil para capítulos de livro.",
    )

    class Meta:
        model = Reference
        fields = (
            "reference_type",
            "title",
            "subtitle",
            "authors_input",
            "editors_input",
            "year",
            "container_title",
            "publisher",
            "publisher_place",
            "edition",
            "volume",
            "issue",
            "pages",
            "doi",
            "url",
            "access_date",
            "language",
            "notes",
        )
        widgets = {
            "access_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["authors_input"].initial = people_to_input(
                self.instance.authors
            )
            self.fields["editors_input"].initial = people_to_input(
                self.instance.editors
            )

    def clean_doi(self):
        doi = self.cleaned_data.get("doi", "").strip()
        for prefix in (
            "https://doi.org/",
            "http://doi.org/",
            "https://dx.doi.org/",
            "doi:",
        ):
            if doi.lower().startswith(prefix):
                doi = doi[len(prefix) :]
                break
        return doi.strip()

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.authors = parse_people(self.cleaned_data.get("authors_input"))
        instance.editors = parse_people(self.cleaned_data.get("editors_input"))
        instance.extraction_status = Reference.ExtractionStatus.REVIEWED
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def clean(self, data, initial=None):
        single_clean = super().clean
        if isinstance(data, (list, tuple)):
            return [single_clean(item, initial) for item in data]
        return [single_clean(data, initial)] if data else []


class ImportSourcesForm(forms.Form):
    files = MultipleFileField(
        label="Arquivos",
        required=False,
        widget=MultipleFileInput(attrs={"accept": ".pdf,.docx,.pptx"}),
        help_text="PDF, DOCX ou PPTX. Até 10 arquivos por envio.",
    )
    urls = forms.CharField(
        label="URLs ou DOIs",
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 5,
                "placeholder": "https://doi.org/10.1000/exemplo\nhttps://periodico.org/artigo",
            }
        ),
        help_text="Informe uma URL por linha. Metadados acadêmicos serão aproveitados quando estiverem disponíveis.",
    )

    def clean_files(self):
        files = self.cleaned_data.get("files", [])
        if len(files) > settings.MAX_FILES_PER_IMPORT:
            raise forms.ValidationError(
                f"Envie no máximo {settings.MAX_FILES_PER_IMPORT} arquivos por vez."
            )
        allowed = {"pdf", "docx", "pptx"}
        for uploaded in files:
            extension = (
                uploaded.name.rsplit(".", 1)[-1].lower() if "." in uploaded.name else ""
            )
            if extension not in allowed:
                raise forms.ValidationError(
                    f"O arquivo “{uploaded.name}” não é PDF, DOCX ou PPTX."
                )
            if uploaded.size > settings.MAX_UPLOAD_FILE_SIZE:
                limit_mb = settings.MAX_UPLOAD_FILE_SIZE // (1024 * 1024)
                raise forms.ValidationError(
                    f"O arquivo “{uploaded.name}” excede o limite de {limit_mb} MB."
                )
            try:
                if extension == "pdf":
                    signature = uploaded.read(5)
                    if signature != b"%PDF-":
                        raise forms.ValidationError(
                            f"O arquivo “{uploaded.name}” não possui uma estrutura PDF válida."
                        )
                else:
                    with ZipFile(uploaded) as archive:
                        members = set(archive.namelist())
                        unpacked_size = sum(
                            item.file_size for item in archive.infolist()
                        )
                    expected = (
                        "word/document.xml"
                        if extension == "docx"
                        else "ppt/presentation.xml"
                    )
                    if expected not in members:
                        raise forms.ValidationError(
                            f"O arquivo “{uploaded.name}” não possui uma estrutura {extension.upper()} válida."
                        )
                    if unpacked_size > 100 * 1024 * 1024 or unpacked_size > max(
                        uploaded.size * 80, 10 * 1024 * 1024
                    ):
                        raise forms.ValidationError(
                            f"O arquivo “{uploaded.name}” expande além do limite seguro."
                        )
            except BadZipFile as exc:
                raise forms.ValidationError(
                    f"O arquivo “{uploaded.name}” está corrompido ou usa uma extensão incorreta."
                ) from exc
            finally:
                uploaded.seek(0)
        return files

    def clean_urls(self):
        raw = self.cleaned_data.get("urls", "")
        urls = [line.strip() for line in raw.splitlines() if line.strip()]
        if len(urls) > 20:
            raise forms.ValidationError("Informe no máximo 20 URLs por vez.")
        return urls

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("files") and not cleaned.get("urls"):
            raise forms.ValidationError(
                "Envie pelo menos um arquivo ou informe uma URL."
            )
        return cleaned
