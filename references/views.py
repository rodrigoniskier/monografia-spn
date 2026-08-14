from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Max, Q
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from .forms import ImportSourcesForm, ProjectForm, ReferenceForm
from .models import CITATION_STYLES, Project, ProjectReference, Reference
from .services.citations import FORMATTERS, generate_citations
from .services.exports import export_docx, export_pdf, export_txt
from .services.extraction import ExtractionResult, extract_file, extract_url

REFERENCE_FIELD_NAMES = {
    "reference_type",
    "authors",
    "editors",
    "title",
    "subtitle",
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
    "language",
    "source_url",
}


def home(request):
    if request.user.is_authenticated:
        return redirect("references:dashboard")
    return render(request, "references/home.html")


@login_required
def dashboard(request):
    projects = (
        Project.objects.filter(owner=request.user)
        .annotate(reference_count=Count("project_references"))
        .order_by("-updated_at")[:5]
    )
    stats = {
        "projects": Project.objects.filter(owner=request.user).count(),
        "references": Reference.objects.filter(owner=request.user).count(),
        "needs_review": Reference.objects.filter(
            owner=request.user, extraction_status=Reference.ExtractionStatus.REVIEW
        ).count(),
    }
    recent_references = Reference.objects.filter(owner=request.user).order_by(
        "-updated_at"
    )[:5]
    return render(
        request,
        "references/dashboard.html",
        {"projects": projects, "stats": stats, "recent_references": recent_references},
    )


@login_required
def project_list(request):
    projects = Project.objects.filter(owner=request.user).annotate(
        reference_count=Count("project_references")
    )
    query = request.GET.get("q", "").strip()
    if query:
        projects = projects.filter(
            Q(name__icontains=query) | Q(description__icontains=query)
        )
    return render(
        request, "references/project_list.html", {"projects": projects, "query": query}
    )


@login_required
def project_create(request):
    form = ProjectForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        project = form.save(commit=False)
        project.owner = request.user
        project.save()
        messages.success(
            request, "Projeto criado. Agora você já pode importar as fontes."
        )
        return redirect("references:import_sources", pk=project.pk)
    return render(
        request, "references/project_form.html", {"form": form, "title": "Novo projeto"}
    )


@login_required
def project_update(request, pk):
    project = get_object_or_404(Project, pk=pk, owner=request.user)
    form = ProjectForm(request.POST or None, instance=project)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Projeto atualizado.")
        return redirect(project)
    return render(
        request,
        "references/project_form.html",
        {"form": form, "project": project, "title": "Editar projeto"},
    )


@login_required
def project_delete(request, pk):
    project = get_object_or_404(Project, pk=pk, owner=request.user)
    if request.method == "POST":
        name = project.name
        project.delete()
        messages.success(
            request,
            f"O projeto “{name}” foi excluído. As referências continuam na sua biblioteca.",
        )
        return redirect("references:project_list")
    return render(
        request,
        "references/confirm_delete.html",
        {
            "object": project,
            "object_label": "projeto",
            "cancel_url": project.get_absolute_url(),
        },
    )


@login_required
def project_detail(request, pk):
    project = get_object_or_404(Project, pk=pk, owner=request.user)
    links = project.project_references.select_related("reference")
    query = request.GET.get("q", "").strip()
    if query:
        links = links.filter(
            Q(reference__title__icontains=query)
            | Q(reference__doi__icontains=query)
            | Q(reference__container_title__icontains=query)
        )
    return render(
        request,
        "references/project_detail.html",
        {"project": project, "links": links, "query": query},
    )


def _next_position(project):
    maximum = project.project_references.aggregate(value=Max("position"))["value"]
    return (maximum or 0) + 1


def _store_extraction(
    user,
    project,
    result: ExtractionResult,
    *,
    source_kind,
    source_file=None,
    source_label="",
):
    fields = {
        key: value
        for key, value in result.fields.items()
        if key in REFERENCE_FIELD_NAMES and value not in (None, "")
    }
    fields["title"] = str(
        fields.get("title") or source_label or "Referência sem título"
    )[:600]
    fields["source_kind"] = source_kind
    fields["extraction_warnings"] = result.warnings
    fields["extraction_status"] = Reference.ExtractionStatus.REVIEW
    if source_label and source_kind != Reference.SourceKind.URL:
        fields["original_filename"] = Path(source_label).name[:255]
    for key in ("subtitle", "container_title"):
        if key in fields:
            fields[key] = str(fields[key])[: 600 if key == "subtitle" else 500]
    for key in (
        "doi",
        "publisher",
        "publisher_place",
        "edition",
        "volume",
        "issue",
        "pages",
        "language",
    ):
        if key in fields:
            fields[key] = str(fields[key])[: Reference._meta.get_field(key).max_length]
    for key in ("url", "source_url"):
        if key in fields:
            fields[key] = str(fields[key])[:1000]

    doi = fields.get("doi", "")
    fingerprint = Reference.make_fingerprint(
        fields["title"], fields.get("year", ""), doi
    )
    existing = None
    if doi:
        existing = Reference.objects.filter(owner=user, doi__iexact=doi).first()
    if not existing:
        existing = Reference.objects.filter(
            owner=user, normalized_fingerprint=fingerprint
        ).first()

    if existing:
        reference = existing
        created = False
    else:
        reference = Reference(owner=user, **fields)
        if source_file:
            reference.source_file = source_file
        reference.save()
        created = True

    _, linked = ProjectReference.objects.get_or_create(
        project=project,
        reference=reference,
        defaults={"position": _next_position(project), "included": True},
    )
    return reference, created, linked


@login_required
def import_sources(request, pk):
    project = get_object_or_404(Project, pk=pk, owner=request.user)
    form = ImportSourcesForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        created_count = 0
        linked_count = 0
        duplicate_count = 0
        with transaction.atomic():
            for uploaded in form.cleaned_data["files"]:
                extension = Path(uploaded.name).suffix.lower().lstrip(".")
                result = extract_file(uploaded)
                _, created, linked = _store_extraction(
                    request.user,
                    project,
                    result,
                    source_kind=extension,
                    source_file=uploaded,
                    source_label=uploaded.name,
                )
                created_count += int(created)
                linked_count += int(linked)
                duplicate_count += int(not created)
            for url in form.cleaned_data["urls"]:
                result = extract_url(url)
                _, created, linked = _store_extraction(
                    request.user,
                    project,
                    result,
                    source_kind=Reference.SourceKind.URL,
                    source_label=url,
                )
                created_count += int(created)
                linked_count += int(linked)
                duplicate_count += int(not created)
        if created_count:
            messages.success(
                request,
                f"{created_count} nova(s) referência(s) importada(s) para revisão.",
            )
        if duplicate_count:
            messages.info(
                request,
                f"{duplicate_count} item(ns) já existia(m) na sua biblioteca e não foi(ram) duplicado(s).",
            )
        if not created_count and not linked_count:
            messages.info(request, "Nenhum item novo foi adicionado ao projeto.")
        return redirect("references:project_detail", pk=project.pk)
    return render(
        request, "references/import_sources.html", {"project": project, "form": form}
    )


@login_required
def reference_list(request):
    references = Reference.objects.filter(owner=request.user).annotate(
        project_count=Count("project_links")
    )
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    if query:
        references = references.filter(
            Q(title__icontains=query)
            | Q(doi__icontains=query)
            | Q(container_title__icontains=query)
        )
    if status in Reference.ExtractionStatus.values:
        references = references.filter(extraction_status=status)
    return render(
        request,
        "references/reference_list.html",
        {"references": references, "query": query, "status": status},
    )


@login_required
def reference_create(request):
    project = None
    project_id = request.GET.get("projeto") or request.POST.get("project_id")
    if project_id:
        project = get_object_or_404(Project, pk=project_id, owner=request.user)
    form = ReferenceForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        reference = form.save(commit=False)
        reference.owner = request.user
        reference.source_kind = Reference.SourceKind.MANUAL
        reference.save()
        if project:
            ProjectReference.objects.get_or_create(
                project=project,
                reference=reference,
                defaults={"position": _next_position(project)},
            )
        messages.success(request, "Referência cadastrada.")
        if project:
            return redirect(project)
        return redirect("references:reference_list")
    return render(
        request,
        "references/reference_form.html",
        {
            "form": form,
            "reference": None,
            "project": project,
            "title": "Nova referência",
        },
    )


@login_required
def reference_edit(request, pk):
    reference = get_object_or_404(Reference, pk=pk, owner=request.user)
    form = ReferenceForm(request.POST or None, instance=reference)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Referência revisada e atualizada.")
        next_url = request.POST.get("next", "")
        if next_url.startswith("/") and not next_url.startswith("//"):
            return redirect(next_url)
        return redirect("references:reference_list")
    return render(
        request,
        "references/reference_form.html",
        {
            "form": form,
            "reference": reference,
            "title": "Revisar referência",
            "next": request.GET.get("next", ""),
        },
    )


@login_required
def reference_delete(request, pk):
    reference = get_object_or_404(Reference, pk=pk, owner=request.user)
    if request.method == "POST":
        title = reference.title
        reference.delete()
        messages.success(
            request, f"A referência “{title}” foi excluída da sua biblioteca."
        )
        return redirect("references:reference_list")
    return render(
        request,
        "references/confirm_delete.html",
        {
            "object": reference,
            "object_label": "referência",
            "cancel_url": reverse("references:reference_list"),
        },
    )


@login_required
def reference_file(request, pk):
    reference = get_object_or_404(Reference, pk=pk, owner=request.user)
    if not reference.source_file:
        raise Http404("Esta referência não possui arquivo original.")
    filename = reference.original_filename or Path(reference.source_file.name).name
    return FileResponse(
        reference.source_file.open("rb"), as_attachment=True, filename=filename
    )


@login_required
def add_existing(request, pk):
    project = get_object_or_404(Project, pk=pk, owner=request.user)
    linked_ids = project.project_references.values_list("reference_id", flat=True)
    available = Reference.objects.filter(owner=request.user).exclude(pk__in=linked_ids)
    query = request.GET.get("q", "").strip()
    if query:
        available = available.filter(
            Q(title__icontains=query) | Q(doi__icontains=query)
        )
    if request.method == "POST":
        selected = Reference.objects.filter(
            owner=request.user, pk__in=request.POST.getlist("references")
        )
        position = _next_position(project)
        count = 0
        for reference in selected:
            _, created = ProjectReference.objects.get_or_create(
                project=project,
                reference=reference,
                defaults={"position": position + count},
            )
            count += int(created)
        messages.success(request, f"{count} referência(s) adicionada(s) ao projeto.")
        return redirect(project)
    return render(
        request,
        "references/add_existing.html",
        {"project": project, "references": available, "query": query},
    )


@require_POST
@login_required
def remove_from_project(request, project_pk, reference_pk):
    project = get_object_or_404(Project, pk=project_pk, owner=request.user)
    link = get_object_or_404(
        ProjectReference, project=project, reference_id=reference_pk
    )
    link.delete()
    messages.success(
        request, "Referência removida deste projeto. Ela permanece na sua biblioteca."
    )
    return redirect(project)


@login_required
def generate_list(request, pk):
    project = get_object_or_404(Project, pk=pk, owner=request.user)
    links = list(project.project_references.select_related("reference"))
    if request.method == "POST":
        style = request.POST.get("style", project.default_style)
        if style not in FORMATTERS:
            style = "abnt"
        selected_ids = set(request.POST.getlist("references"))
        with transaction.atomic():
            project.default_style = style
            project.save(update_fields=["default_style", "updated_at"])
            for link in links:
                included = str(link.reference_id) in selected_ids
                try:
                    position = max(
                        0,
                        min(
                            10000,
                            int(
                                request.POST.get(
                                    f"position_{link.reference_id}", link.position
                                )
                            ),
                        ),
                    )
                except (TypeError, ValueError):
                    position = link.position
                changed_fields = []
                if link.included != included:
                    link.included = included
                    changed_fields.append("included")
                if link.position != position:
                    link.position = position
                    changed_fields.append("position")
                if changed_fields:
                    link.save(update_fields=changed_fields)
        messages.success(request, "Seleção e estilo salvos.")
        return redirect("references:generate_list", pk=project.pk)

    included_references = [link.reference for link in links if link.included]
    citations = generate_citations(included_references, project.default_style)
    return render(
        request,
        "references/generate_list.html",
        {
            "project": project,
            "links": links,
            "citations": citations,
            "citation_styles": CITATION_STYLES,
        },
    )


@login_required
def export_project(request, pk, file_format):
    project = get_object_or_404(Project, pk=pk, owner=request.user)
    references = [
        link.reference
        for link in project.project_references.select_related("reference")
        if link.included
    ]
    if not references:
        messages.error(request, "Selecione ao menos uma referência antes de exportar.")
        return redirect("references:generate_list", pk=project.pk)
    generators = {
        "txt": (export_txt, "text/plain; charset=utf-8"),
        "docx": (
            export_docx,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
        "pdf": (export_pdf, "application/pdf"),
    }
    if file_format not in generators:
        raise Http404("Formato de exportação inválido.")
    generator, content_type = generators[file_format]
    if file_format == "txt":
        content = generator(references, project.default_style)
    else:
        content = generator(references, project.default_style, project.name)
    filename = f"referencias-{slugify(project.name) or 'projeto'}-{project.default_style}.{file_format}"
    response = HttpResponse(content, content_type=content_type)
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
