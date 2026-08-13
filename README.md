# Monografia SPN

Aplicativo web para orientar alunos do Seminário Presbiteriano do Norte (SPN) desde a delimitação do tema até a geração da monografia em DOCX. Cada usuário possui conta própria, progresso salvo, roteiro por etapa, revisão acadêmica assistida pela Gemini API e pesquisa bibliográfica em catálogos reais.

## O que já está implementado

- cadastro, login e isolamento dos trabalhos por usuário;
- apresentação inicial em carrossel com orientação objetiva;
- menu lateral com todas as partes da monografia;
- planejamento do tema, delimitação, problema, hipótese, objetivos, justificativa e metodologia;
- elementos pré-textuais observados no padrão institucional do SPN, inclusive base confessional;
- desenvolvimento em seções e subseções de até cinco níveis;
- salvamento automático e indicador de progresso;
- revisão pela Gemini API com proposta separada do texto original e aceite explícito do autor;
- pesquisa simultânea em Crossref, OpenAlex, Google Books e Open Library;
- resultados assinados pelo servidor e aceitação apenas de links HTTPS de domínios acadêmicos conhecidos;
- referências formatadas e indicação autor-data;
- exportação DOCX em A4, Times New Roman 12, margens 3/2 cm, entrelinha 1,5, paginação, sumário e estrutura acadêmica;
- interface responsiva e sem dependência de CDN.

## Padrão acadêmico adotado

A estrutura combina os elementos recorrentes das monografias fornecidas pelo SPN com as normas vigentes:

- ABNT NBR 14724:2024, versão corrigida em 2025 — apresentação de trabalhos acadêmicos;
- ABNT NBR 6023:2025 — referências;
- ABNT NBR 10520:2023 — citações;
- ABNT NBR 6028:2021 — resumos;
- ABNT NBR 6024:2012 — numeração progressiva das seções;
- ABNT NBR 6027:2012 — sumário.

O aplicativo usa **seções**, e não capítulos, e preserva particularidades institucionais do SPN sem reproduzir inconsistências formais encontradas em trabalhos anteriores.

## Tecnologia

- Python 3.12+
- Django 5.2 LTS
- SQLite
- `google-genai` (Gemini Interactions API, com fallback de compatibilidade)
- `python-docx`
- WhiteNoise

## Execução local

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
.venv/bin/python manage.py migrate
.venv/bin/python manage.py runserver
```

Acesse `http://127.0.0.1:8000/`.

## Configuração

As configurações ficam em um arquivo `.env`, que não é versionado. Variáveis principais:

| Variável | Finalidade |
|---|---|
| `APP_ENV` | Use `production` no servidor |
| `DJANGO_SECRET_KEY` | Chave aleatória e privada do Django |
| `DJANGO_DEBUG` | Deve ser `false` em produção |
| `DJANGO_ALLOWED_HOSTS` | Hosts aceitos pelo Django |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Origem HTTPS do site |
| `GEMINI_API_KEY` | Chave privada da Gemini API, usada somente no backend |
| `GEMINI_MODEL` | Modelo principal; padrão `gemini-3.6-flash` |
| `GEMINI_FALLBACK_MODEL` | Modelo alternativo; padrão `gemini-3.5-flash-lite` |
| `SQLITE_PATH` | Caminho opcional do banco SQLite |
| `CACHE_PATH` | Caminho opcional do cache local |
| `RESEARCH_CONTACT_EMAIL` | Identificação cortês para APIs acadêmicas |

Nunca coloque a chave Gemini em JavaScript, templates, commits ou mensagens de log.

## Como a revisão por IA funciona

O texto do usuário é enviado pelo backend, com limite de tamanho e de frequência. A resposta obedece a um esquema estruturado e contém:

- texto revisado completo;
- resumo das intervenções;
- sugestões justificadas e priorizadas;
- alertas de fonte, citação ou precisão;
- indicação de preservação da voz autoral.

A proposta não sobrescreve automaticamente o trabalho. O autor precisa aceitá-la, e o sistema recusa o aceite se o texto tiver sido alterado depois da análise. O prompt proíbe invenção de obras, DOI, páginas, citações, fatos e referências bíblicas.

## Pesquisa de publicações

O metabuscador consulta APIs públicas de catálogos reconhecidos. Os resultados são ordenados pela relação com a consulta e pelos metadados disponíveis. Um link real comprova que o registro existe, mas o aluno ainda deve ler a obra e conferir autoria, edição, páginas e pertinência antes de citá-la.

## Testes

```bash
.venv/bin/python manage.py test
.venv/bin/python manage.py check
```

Os testes cobrem acesso por proprietário, salvamento, hierarquia de seções, aceite seguro de revisão, assinatura de resultados bibliográficos, validação de URLs, contrato da Gemini API e estrutura do DOCX.

## Implantação no PythonAnywhere

O roteiro específico da conta `monografiaspn` está em [deploy/PYTHONANYWHERE.md](deploy/PYTHONANYWHERE.md). Depois da primeira implantação, atualizações podem ser aplicadas com:

```bash
bash deploy/update_pythonanywhere.sh
```

O recarregamento do Web App continua sendo feito no painel do PythonAnywhere.

