"""Gateway seguro e resiliente para revisão acadêmica com a Gemini API."""

from __future__ import annotations

from hashlib import sha256
import json
import logging
import random
import re
import time
from typing import Literal

from django.conf import settings
from django.core.cache import cache
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


logger = logging.getLogger("works.ai")

MAX_INPUT_CHARS = 20_000
RATE_WINDOW_SECONDS = 15 * 60
RATE_LIMIT = 12
CIRCUIT_FAILURE_LIMIT = 4
CIRCUIT_COOLDOWN_SECONDS = 120


class RevisionSuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: Literal[
        "clareza", "coesão", "argumentação", "registro acadêmico", "gramática",
        "citação", "estrutura", "precisão"
    ]
    original_excerpt: str = Field(default="", max_length=500)
    proposed_change: str = Field(default="", max_length=800)
    reason: str = Field(min_length=3, max_length=800)
    priority: Literal["alta", "média", "baixa"]


class AcademicRevision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    revised_text: str
    summary: str = Field(min_length=3, max_length=1000)
    suggestions: list[RevisionSuggestion] = Field(default_factory=list, max_length=12)
    warnings: list[str] = Field(default_factory=list, max_length=10)
    voice_preserved: bool
    confidence: float = Field(ge=0, le=1)

    @field_validator("revised_text")
    @classmethod
    def revised_text_not_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("O texto revisado não pode ficar vazio.")
        return value.strip()


class AIGatewayError(RuntimeError):
    def __init__(self, message: str, *, code: str = "unavailable"):
        super().__init__(message)
        self.code = code


SYSTEM_INSTRUCTION = """
Você é um revisor acadêmico brasileiro especializado em teologia e metodologia
científica. Trabalhe como revisor, nunca como coautor oculto. Preserve a voz, o
vocabulário teológico, a posição confessional e o estilo pessoal do autor.

Regras invioláveis:
1. Não invente fatos, autores, obras, DOI, ISBN, páginas, datas, citações ou
   referências bíblicas. Quando algo exigir fonte, registre um alerta.
2. Não altere o conteúdo de citações diretas nem números de página. Se perceber
   possível erro, mantenha a transcrição e apenas sinalize.
3. Não mude a tese ou a posição teológica do autor. Aponte lacunas como sugestão.
4. Corrija gramática, clareza, coesão, redundância e registro acadêmico com a
   menor intervenção necessária.
5. Prefira linguagem natural e precisa; não homogeneíze o texto em estilo de IA.
6. Siga a ABNT atual: use “seção” e “subseção”, não “capítulo”, para divisões do
   trabalho acadêmico; use autor-data sem sobrenome integralmente em caixa-alta.
7. A resposta deve obedecer exatamente ao esquema estruturado solicitado.
""".strip()


ACTION_INSTRUCTIONS = {
    "review": "Analise o texto e proponha uma revisão conservadora, explicando as mudanças mais úteis.",
    "polish": "Aprimore o registro acadêmico e a fluidez com intervenção mínima e sem apagar a voz do autor.",
    "outline": "Preserve o texto e proponha principalmente melhorias de organização, sequência e transição.",
    "translate": "Produza uma tradução acadêmica fiel para o inglês, preservando termos próprios e sinalizando escolhas terminológicas incertas.",
}


def _rate_limit(user_id: int) -> None:
    key = f"ai-rate:{user_id}"
    try:
        current = cache.get(key)
        if current is None:
            cache.set(key, 1, RATE_WINDOW_SECONDS)
            return
        if int(current) >= RATE_LIMIT:
            raise AIGatewayError(
                "Limite temporário de revisões atingido. Aguarde alguns minutos antes de tentar novamente.",
                code="rate_limit",
            )
        cache.incr(key)
    except AIGatewayError:
        raise
    except Exception:
        logger.warning("Falha não bloqueante no limitador de uso", exc_info=True)


def _circuit_open() -> bool:
    opened_at = cache.get("ai-circuit-opened")
    if not opened_at:
        return False
    if time.time() - float(opened_at) >= CIRCUIT_COOLDOWN_SECONDS:
        cache.delete_many(["ai-circuit-opened", "ai-circuit-failures"])
        return False
    return True


def _record_failure() -> None:
    try:
        failures = cache.get("ai-circuit-failures", 0) + 1
        cache.set("ai-circuit-failures", failures, CIRCUIT_COOLDOWN_SECONDS * 2)
        if failures >= CIRCUIT_FAILURE_LIMIT:
            cache.set("ai-circuit-opened", time.time(), CIRCUIT_COOLDOWN_SECONDS)
    except Exception:
        logger.warning("Falha ao atualizar circuit breaker", exc_info=True)


def _record_success() -> None:
    cache.delete_many(["ai-circuit-opened", "ai-circuit-failures"])


def _extract_text(response) -> str:
    """Aceita tanto Interactions API quanto generate_content como defesa de compatibilidade."""
    output_text = getattr(response, "output_text", None)
    if output_text:
        return str(output_text)
    direct = getattr(response, "text", None)
    if direct:
        return str(direct)
    outputs = getattr(response, "outputs", None) or []
    chunks = []
    for output in outputs:
        text = getattr(output, "text", None)
        if text:
            chunks.append(str(text))
            continue
        content = getattr(output, "content", None)
        for part in getattr(content, "parts", None) or []:
            if getattr(part, "text", None):
                chunks.append(str(part.text))
    if chunks:
        return "\n".join(chunks)
    parsed = getattr(response, "parsed", None)
    if parsed:
        if isinstance(parsed, BaseModel):
            return parsed.model_dump_json()
        return json.dumps(parsed, ensure_ascii=False)
    raise AIGatewayError("A Gemini API respondeu sem conteúdo utilizável.", code="invalid_response")


def _parse_structured(response) -> AcademicRevision:
    parsed = getattr(response, "parsed", None)
    if parsed:
        return parsed if isinstance(parsed, AcademicRevision) else AcademicRevision.model_validate(parsed)
    raw = _extract_text(response).strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I | re.S)
    return AcademicRevision.model_validate_json(raw)


def _call_interactions(client, model: str, prompt: str):
    schema = AcademicRevision.model_json_schema()
    return client.interactions.create(
        model=model,
        input=prompt,
        system_instruction=SYSTEM_INSTRUCTION,
        generation_config={"max_output_tokens": 8192},
        response_format={
            "type": "text",
            "mime_type": "application/json",
            "schema": schema,
        },
        store=False,
    )


def _call_generate_content(client, model: str, prompt: str):
    from google.genai import types

    return client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            temperature=0.2,
            max_output_tokens=8192,
            response_mime_type="application/json",
            response_schema=AcademicRevision,
        ),
    )


def _call_model(client, model: str, prompt: str):
    interactions = getattr(client, "interactions", None)
    if interactions and hasattr(interactions, "create"):
        try:
            return _call_interactions(client, model, prompt)
        except (TypeError, AttributeError) as exc:
            logger.info("Interactions API incompatível com o SDK instalado; usando generate_content: %s", exc)
    return _call_generate_content(client, model, prompt)


def _is_retryable(exc: Exception) -> bool:
    text = str(exc).lower()
    retry_markers = ("429", "500", "502", "503", "504", "timeout", "tempor", "unavailable", "reset")
    return any(marker in text for marker in retry_markers)


def revise_text(*, user_id: int, target_label: str, action: str, text: str) -> tuple[AcademicRevision, str]:
    text = str(text or "").strip()
    if not settings.GEMINI_API_KEY:
        raise AIGatewayError(
            "A revisão por IA ainda não foi configurada. O administrador deve definir GEMINI_API_KEY no servidor.",
            code="not_configured",
        )
    if action not in ACTION_INSTRUCTIONS:
        raise AIGatewayError("Tipo de revisão inválido.", code="invalid_request")
    if len(text) < 20:
        raise AIGatewayError("Digite um texto um pouco mais desenvolvido antes de solicitar a revisão.", code="invalid_request")
    if len(text) > MAX_INPUT_CHARS:
        raise AIGatewayError(
            f"Revise até {MAX_INPUT_CHARS:,} caracteres por vez.".replace(",", "."),
            code="too_large",
        )
    if _circuit_open():
        raise AIGatewayError("A revisão por IA está se recuperando de uma indisponibilidade. Tente novamente em instantes.", code="circuit_open")
    _rate_limit(user_id)

    digest = sha256(text.encode("utf-8")).hexdigest()[:12]
    prompt = (
        f"Tarefa: {ACTION_INSTRUCTIONS[action]}\n"
        f"Parte do trabalho: {target_label}.\n"
        "Retorne o texto completo revisado e sugestões específicas. "
        "Mantenha todo marcador de citação, nota, versículo e citação direta.\n\n"
        f"TEXTO DO AUTOR:\n{text}"
    )

    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise AIGatewayError("O componente da Gemini API não está instalado no servidor.", code="not_configured") from exc

    client = genai.Client(
        api_key=settings.GEMINI_API_KEY,
        http_options=types.HttpOptions(timeout=settings.GEMINI_TIMEOUT_MS),
    )
    models = [settings.GEMINI_MODEL]
    if settings.GEMINI_FALLBACK_MODEL and settings.GEMINI_FALLBACK_MODEL not in models:
        models.append(settings.GEMINI_FALLBACK_MODEL)
    last_error = None

    for model in models:
        for attempt in range(3):
            started = time.monotonic()
            try:
                response = _call_model(client, model, prompt)
                try:
                    result = _parse_structured(response)
                except (ValidationError, json.JSONDecodeError, ValueError) as parse_error:
                    if attempt == 0:
                        repair_prompt = (
                            prompt + "\n\nA resposta anterior não respeitou o esquema. "
                            "Responda novamente com JSON estritamente válido e todos os campos obrigatórios."
                        )
                        response = _call_model(client, model, repair_prompt)
                        result = _parse_structured(response)
                    else:
                        raise parse_error
                if len(result.revised_text) > MAX_INPUT_CHARS * 2:
                    raise AIGatewayError("A resposta da IA excedeu o limite seguro.", code="invalid_response")
                _record_success()
                logger.info(
                    "Revisão Gemini concluída model=%s action=%s chars=%s digest=%s duration_ms=%s",
                    model, action, len(text), digest, round((time.monotonic() - started) * 1000),
                )
                return result, model
            except AIGatewayError:
                raise
            except Exception as exc:
                last_error = exc
                retryable = _is_retryable(exc)
                logger.warning(
                    "Falha Gemini model=%s attempt=%s retryable=%s digest=%s: %s",
                    model, attempt + 1, retryable, digest, exc,
                )
                if not retryable:
                    break
                if attempt < 2:
                    time.sleep((0.65 * (2**attempt)) + random.uniform(0.05, 0.35))

    _record_failure()
    error_text = str(last_error or "erro desconhecido").lower()
    if "api key" in error_text or "401" in error_text or "403" in error_text:
        message = "A chave da Gemini API foi recusada. O administrador precisa revisar a configuração."
        code = "authentication"
    elif "429" in error_text or "quota" in error_text:
        message = "A cota da Gemini API está temporariamente indisponível. Tente novamente mais tarde."
        code = "quota"
    else:
        message = "Não foi possível concluir a revisão agora. Seu texto continua salvo; tente novamente em instantes."
        code = "unavailable"
    raise AIGatewayError(message, code=code) from last_error
