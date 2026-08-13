from __future__ import annotations

from datetime import date
import json
import logging
from types import SimpleNamespace

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core import signing
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Max
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .forms import RegisterForm
from .guidance import AI_FIELDS, EDITABLE_FIELDS, GROUPS, ONBOARDING_SLIDES, PARTS
from .models import AIRevision, Monograph, Profile, Publication, Section
from .services.abnt import citation_label, format_reference, trusted_publication_url
from .services.ai_gateway import AIGatewayError, revise_text
from .services.docx_export import build_monograph_docx
from .services.research import search_publications


logger = logging.getLogger("works")
RESEARCH_SIGNING_SALT = "monografia-spn-publication-v1"
MAX_TEXT_LENGTH = 120_000
RESEARCH_RATE_LIMIT = 30
RESEARCH_RATE_WINDOW = 15 * 60


def _json_body(request):
    try:
        return json.loads(request.body or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError("A requisição não contém JSON válido.") from exc


def _json_error(message, *, status=400, code="invalid_request"):
    return JsonResponse({"ok": False, "error": str(message), "code": code}, status=status)


def _rate_limit_exceeded(*, namespace: str, user_id: int, limit: int, window: int) -> bool:
    """Limitador simples que falha aberto se o cache do servidor estiver indisponível."""
    key = f"{namespace}:{user_id}"
    try:
        current = cache.get(key)
        if current is None:
            cache.set(key, 1, window)
            return False
        if int(current) >= limit:
            return True
        cache.incr(key)
    except Exception:
        logger.warning("Falha não bloqueante no limitador %s", namespace, exc_info=True)
    return False


def _owned_work(request, pk):
    return get_object_or_404(Monograph.objects.select_related("owner"), pk=pk, owner=request.user)


def _profile(user):
    full_name = user.get_full_name().strip() or user.username
    profile, _ = Profile.objects.get_or_create(user=user, defaults={"full_name": full_name})
    return profile


def _sidebar_groups():
    return GROUPS


def _field_value(work, field_config):
    value = getattr(work, field_config["name"])
    if isinstance(value, date):
        return value.isoformat()
    return value


def _export_checks(work):
    main_sections = work.sections.filter(parent__isnull=True)
    return [
        {"label": "Autor e título informados", "done": bool(work.author_name.strip() and work.title.strip())},
        {"label": "Problema, objetivos e método preenchidos", "done": all(bool(value.strip()) for value in [work.research_problem, work.general_objective, work.specific_objectives, work.methodology])},
        {"label": "Introdução preenchida", "done": bool(work.introduction.strip())},
        {"label": "Seções de desenvolvimento preenchidas", "done": main_sections.exists() and not main_sections.filter(content="").exists()},
        {"label": "Considerações finais preenchidas", "done": bool(work.conclusion.strip())},
        {"label": "Resumo e palavras-chave preenchidos", "done": bool(work.abstract_pt.strip() and work.keywords_pt.strip())},
        {"label": "Ao menos uma referência salva", "done": work.publications.exists()},
    ]


def home(request):
    if not request.user.is_authenticated:
        return redirect("login")
    if not _profile(request.user).onboarding_seen:
        return redirect("works:onboarding")
    return redirect("works:dashboard")


@require_http_methods(["GET", "POST"])
def register(request):
    if request.user.is_authenticated:
        return redirect("works:home")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect("works:onboarding")
    return render(request, "registration/register.html", {"form": form})


@login_required
@require_http_methods(["GET", "POST"])
def onboarding(request):
    profile = _profile(request.user)
    if request.method == "POST":
        profile.onboarding_seen = True
        profile.save(update_fields=["onboarding_seen", "updated_at"])
        return redirect("works:dashboard")
    return render(request, "works/onboarding.html", {"slides": ONBOARDING_SLIDES})


@login_required
@require_GET
def dashboard(request):
    works = request.user.monographs.all().prefetch_related("sections")
    return render(request, "works/dashboard.html", {"monographs": works})


@login_required
@require_POST
@transaction.atomic
def create_monograph(request):
    profile = _profile(request.user)
    work = Monograph.objects.create(owner=request.user, author_name=profile.full_name)
    starter_sections = [
        ("Contexto histórico e delimitação conceitual", "historical"),
        ("Fundamentos bíblico-teológicos e confessionais", "biblical-theological"),
        ("Implicações pastorais e contemporâneas", "pastoral"),
    ]
    Section.objects.bulk_create([
        Section(monograph=work, title=title, guidance_key=key, order=index, level=1)
        for index, (title, key) in enumerate(starter_sections, start=1)
    ])
    messages.success(request, "Sua monografia foi criada. Comece delimitando o tema.")
    return redirect("works:workspace", pk=work.pk, part_slug="planejamento")


@login_required
@require_POST
def delete_monograph(request, pk):
    work = _owned_work(request, pk)
    title = work.display_title
    work.delete()
    messages.success(request, f'“{title}” foi excluída.')
    return redirect("works:dashboard")


@login_required
@require_GET
def workspace(request, pk, part_slug):
    work = _owned_work(request, pk)
    if part_slug not in PARTS:
        raise Http404("Parte da monografia não encontrada.")
    part = PARTS[part_slug]
    entries = [{**item, "value": _field_value(work, item)} for item in part.get("fields", [])]
    context = {
        "work": work,
        "part": part,
        "part_slug": part_slug,
        "fields": entries,
        "sidebar_groups": _sidebar_groups(),
        "all_works": request.user.monographs.all(),
        "sections": work.sections.filter(parent__isnull=True).prefetch_related("children__children__children__children"),
        "publications": work.publications.all(),
        "ai_revisions": work.ai_revisions.filter(user=request.user)[:8],
        "initial_query": work.research_query,
    }
    if part_slug == "referencias":
        context["reference_rows"] = [
            {"publication": publication, "formatted": format_reference(publication), "citation": citation_label(publication)}
            for publication in work.publications.all()
        ]
    if part_slug == "exportar":
        context["export_checks"] = _export_checks(work)
    template = part.get("template", "works/workspace.html")
    return render(request, template, context)


@login_required
@require_POST
def autosave(request, pk):
    work = _owned_work(request, pk)
    try:
        payload = _json_body(request)
        field_name = str(payload.get("field") or "")
        value = payload.get("value", "")
        if field_name not in EDITABLE_FIELDS:
            return _json_error("Campo não permitido.", status=403, code="forbidden")
        model_field = Monograph._meta.get_field(field_name)
        if field_name == "year":
            value = int(value)
        elif field_name == "approval_date":
            value = date.fromisoformat(value) if value else None
        else:
            value = str(value or "")
            limit = getattr(model_field, "max_length", None) or MAX_TEXT_LENGTH
            if len(value) > min(limit, MAX_TEXT_LENGTH):
                return _json_error("O conteúdo excede o limite deste campo.", code="too_large")
        setattr(work, field_name, value)
        work.full_clean(exclude=[field.name for field in Monograph._meta.fields if field.name not in {field_name, "owner"}])
        work.save(update_fields=[field_name, "updated_at"])
        return JsonResponse({"ok": True, "saved_at": work.updated_at.isoformat(), "completion": work.completion_percentage})
    except (ValueError, TypeError, ValidationError) as exc:
        message = getattr(exc, "message_dict", None) or str(exc)
        return _json_error(message)


@login_required
@require_POST
@transaction.atomic
def add_section(request, pk):
    work = _owned_work(request, pk)
    if work.sections.count() >= 60:
        return _json_error("Limite de 60 seções e subseções atingido.", code="too_many")
    try:
        payload = _json_body(request)
        parent_id = payload.get("parent_id")
        parent = None
        if parent_id:
            parent = get_object_or_404(Section, pk=int(parent_id), monograph=work)
            if parent.level >= 5:
                return _json_error("A ABNT admite hierarquia até a seção quinária.")
        level = parent.level + 1 if parent else 1
        siblings = work.sections.filter(parent=parent)
        order = (siblings.aggregate(value=Max("order"))["value"] or 0) + 1
        title = str(payload.get("title") or "Nova subseção" if parent else payload.get("title") or "Nova seção").strip()[:300]
        section = Section(monograph=work, parent=parent, title=title, level=level, order=order)
        section.full_clean()
        section.save()
        return JsonResponse({"ok": True, "section": {"id": section.pk, "title": section.title, "level": section.level, "parent_id": section.parent_id}})
    except (ValueError, TypeError, ValidationError) as exc:
        return _json_error(str(exc))


@login_required
@require_POST
def update_section(request, pk, section_id):
    work = _owned_work(request, pk)
    section = get_object_or_404(Section, pk=section_id, monograph=work)
    try:
        payload = _json_body(request)
        field_name = str(payload.get("field") or "")
        if field_name not in {"title", "content"}:
            return _json_error("Campo de seção não permitido.", status=403)
        value = str(payload.get("value") or "")
        limit = 300 if field_name == "title" else MAX_TEXT_LENGTH
        if not value.strip() and field_name == "title":
            return _json_error("A seção precisa de um título.")
        if len(value) > limit:
            return _json_error("O conteúdo excede o limite permitido.", code="too_large")
        setattr(section, field_name, value.strip() if field_name == "title" else value)
        section.full_clean()
        section.save(update_fields=[field_name, "updated_at"])
        Monograph.objects.filter(pk=work.pk).update(updated_at=section.updated_at)
        return JsonResponse({"ok": True, "saved_at": section.updated_at.isoformat(), "completion": work.completion_percentage})
    except (ValueError, ValidationError) as exc:
        return _json_error(str(exc))


@login_required
@require_POST
def delete_section(request, pk, section_id):
    work = _owned_work(request, pk)
    section = get_object_or_404(Section, pk=section_id, monograph=work)
    section.delete()
    Monograph.objects.filter(pk=work.pk).update(updated_at=timezone.now())
    return JsonResponse({"ok": True, "completion": work.completion_percentage})


def _revision_target(work, payload):
    target_type = str(payload.get("target_type") or "monograph")
    if target_type == "section":
        section = get_object_or_404(Section, pk=int(payload.get("section_id")), monograph=work)
        return f"section:{section.pk}", section.title, section.content
    field_name = str(payload.get("field") or "")
    if field_name not in AI_FIELDS:
        raise ValueError("Este campo não pode ser enviado para revisão.")
    label = Monograph._meta.get_field(field_name).verbose_name.replace("_", " ").capitalize()
    return f"monograph:{field_name}", label, getattr(work, field_name)


@login_required
@require_POST
def ai_review(request, pk):
    work = _owned_work(request, pk)
    try:
        payload = _json_body(request)
        target_key, target_label, original = _revision_target(work, payload)
        action = str(payload.get("action") or "review")
        result, model = revise_text(user_id=request.user.pk, target_label=target_label, action=action, text=original)
        revision = AIRevision.objects.create(
            monograph=work, user=request.user, target_key=target_key, action=action,
            original_text=original, proposed_text=result.revised_text,
            suggestions=[item.model_dump() for item in result.suggestions],
            warnings=result.warnings, model_name=model,
        )
        return JsonResponse({
            "ok": True,
            "revision": {
                "id": revision.pk, "summary": result.summary,
                "proposed_text": result.revised_text,
                "suggestions": revision.suggestions, "warnings": revision.warnings,
                "voice_preserved": result.voice_preserved, "confidence": result.confidence,
                "accept_url": reverse("works:accept_revision", args=[work.pk, revision.pk]),
            },
        })
    except AIGatewayError as exc:
        status = 429 if exc.code == "rate_limit" else 503 if exc.code in {"unavailable", "circuit_open", "quota"} else 400
        return _json_error(str(exc), status=status, code=exc.code)
    except (ValueError, TypeError) as exc:
        return _json_error(str(exc))


@login_required
@require_POST
@transaction.atomic
def accept_revision(request, pk, revision_id):
    work = _owned_work(request, pk)
    revision = get_object_or_404(AIRevision, pk=revision_id, monograph=work, user=request.user)
    if revision.accepted:
        return _json_error("Esta revisão já foi aplicada.", code="already_applied")
    try:
        target_type, target_id = revision.target_key.split(":", 1)
        if target_type == "section":
            target = get_object_or_404(Section, pk=int(target_id), monograph=work)
            if target.content != revision.original_text:
                return _json_error("O texto mudou após a revisão. Solicite uma nova análise para não sobrescrever suas alterações.", status=409, code="stale")
            target.content = revision.proposed_text
            target.save(update_fields=["content", "updated_at"])
        else:
            if target_id not in AI_FIELDS:
                return _json_error("Destino da revisão inválido.", status=403)
            if getattr(work, target_id) != revision.original_text:
                return _json_error("O texto mudou após a revisão. Solicite uma nova análise para não sobrescrever suas alterações.", status=409, code="stale")
            setattr(work, target_id, revision.proposed_text)
            work.save(update_fields=[target_id, "updated_at"])
        revision.accepted = True
        revision.save(update_fields=["accepted"])
        return JsonResponse({"ok": True, "text": revision.proposed_text, "completion": work.completion_percentage})
    except (ValueError, TypeError) as exc:
        return _json_error(str(exc))


@login_required
@require_POST
def research_search(request, pk):
    work = _owned_work(request, pk)
    if _rate_limit_exceeded(
        namespace="research-rate",
        user_id=request.user.pk,
        limit=RESEARCH_RATE_LIMIT,
        window=RESEARCH_RATE_WINDOW,
    ):
        return _json_error(
            "Limite temporário de pesquisas atingido. Aguarde alguns minutos antes de tentar novamente.",
            status=429,
            code="rate_limit",
        )
    try:
        payload = _json_body(request)
        query = str(payload.get("query") or work.research_query)
        mode = str(payload.get("mode") or "all")
        if mode not in {"all", "classic", "modern"}:
            mode = "all"
        results, warnings = search_publications(query, mode)
        enriched = []
        for result in results:
            token = signing.dumps(result, salt=RESEARCH_SIGNING_SALT, compress=True)
            preview = SimpleNamespace(**result, access_date=date.today())
            enriched.append({**result, "token": token, "reference": format_reference(preview)})
        return JsonResponse({"ok": True, "results": enriched, "warnings": warnings, "query": query})
    except ValueError as exc:
        return _json_error(str(exc))


@login_required
@require_POST
def save_publication(request, pk):
    work = _owned_work(request, pk)
    try:
        payload = _json_body(request)
        data = signing.loads(str(payload.get("token") or ""), salt=RESEARCH_SIGNING_SALT, max_age=2 * 60 * 60)
        if not isinstance(data, dict) or not trusted_publication_url(str(data.get("url") or "")):
            return _json_error("A publicação não possui um link verificável.")
        allowed_fields = {
            "source_type", "title", "subtitle", "authors", "year", "city", "publisher", "edition",
            "container_title", "volume", "issue", "pages", "doi", "isbn", "url", "language", "provider",
        }
        values = {key: data.get(key) for key in allowed_fields if key in data}
        values["raw_metadata"] = data
        publication = Publication(monograph=work, **values)
        publication.full_clean()
        publication.save()
        Monograph.objects.filter(pk=work.pk).update(updated_at=timezone.now())
        return JsonResponse({"ok": True, "publication": {"id": publication.pk, "title": publication.title, "reference": format_reference(publication), "citation": citation_label(publication)}})
    except signing.BadSignature:
        return _json_error("O resultado de pesquisa expirou ou foi alterado. Faça a pesquisa novamente.", status=403, code="bad_signature")
    except IntegrityError:
        return _json_error("Esta publicação já está salva na monografia.", status=409, code="duplicate")
    except (TypeError, ValueError, ValidationError) as exc:
        return _json_error(str(exc))


@login_required
@require_POST
def delete_publication(request, pk, publication_id):
    work = _owned_work(request, pk)
    publication = get_object_or_404(Publication, pk=publication_id, monograph=work)
    publication.delete()
    Monograph.objects.filter(pk=work.pk).update(updated_at=timezone.now())
    return JsonResponse({"ok": True})


@login_required
@require_GET
def export_docx(request, pk):
    work = _owned_work(request, pk)
    try:
        output = build_monograph_docx(work)
    except Exception:
        logger.exception("Falha ao exportar DOCX monograph=%s user=%s", work.pk, request.user.pk)
        messages.error(request, "Não foi possível gerar o DOCX. Seus dados permanecem salvos.")
        return redirect("works:workspace", pk=work.pk, part_slug="exportar")
    filename = slugify(work.title or "monografia-spn")[:90] or "monografia-spn"
    response = HttpResponse(output.getvalue(), content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    response["Content-Disposition"] = f'attachment; filename="{filename}.docx"'
    response["Cache-Control"] = "private, no-store"
    return response
