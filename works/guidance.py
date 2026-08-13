"""Mapa editorial e orientações de escrita da Monografia SPN."""

from collections import OrderedDict


def field(name, label, *, rows=6, placeholder="", help_text="", kind="textarea"):
    return {
        "name": name,
        "label": label,
        "rows": rows,
        "placeholder": placeholder,
        "help": help_text,
        "kind": kind,
    }


PARTS = OrderedDict(
    [
        (
            "planejamento",
            {
                "label": "Tema e projeto",
                "short_label": "Tema e projeto",
                "group": "Planejamento",
                "eyebrow": "Comece por aqui",
                "description": (
                    "Transforme um interesse amplo em uma pergunta teológica viável. "
                    "Esses dados orientarão todas as seções seguintes."
                ),
                "tip": (
                    "Delimite assunto, perspectiva teológica, recorte histórico ou "
                    "contextual e corpus de análise. Um bom problema pede investigação; "
                    "não pode ser respondido apenas com “sim” ou “não”."
                ),
                "checklist": [
                    "O tema cabe no tempo e nas fontes disponíveis?",
                    "O problema está formulado como pergunta clara?",
                    "O objetivo geral responde diretamente ao problema?",
                    "Os objetivos específicos descrevem etapas verificáveis?",
                ],
                "fields": [
                    field("theme", "Tema", rows=3, placeholder="Ex.: A pregação cristocêntrica na pós-modernidade"),
                    field("delimitation", "Delimitação do tema", rows=4, placeholder="Indique o recorte teológico, histórico, geográfico ou documental."),
                    field("research_problem", "Problema de pesquisa", rows=4, placeholder="Formule uma pergunta central que a monografia buscará responder."),
                    field("hypothesis", "Hipótese ou resposta provisória", rows=4, placeholder="Opcional: apresente a resposta que será examinada ao longo da pesquisa."),
                    field("general_objective", "Objetivo geral", rows=3, placeholder="Use um verbo no infinitivo: analisar, compreender, demonstrar, investigar…"),
                    field("specific_objectives", "Objetivos específicos", rows=6, placeholder="Um objetivo por linha, em sequência lógica."),
                    field("justification", "Justificativa", rows=7, placeholder="Explique a relevância acadêmica, eclesial, pastoral e social da pesquisa."),
                    field("methodology", "Metodologia", rows=7, placeholder="Descreva abordagem, fontes, critérios de seleção e percurso de análise."),
                    field("planning_keywords", "Termos de pesquisa", rows=2, kind="text", placeholder="Separe por ponto e vírgula."),
                ],
            },
        ),
        (
            "identificacao",
            {
                "label": "Identificação",
                "short_label": "Identificação",
                "group": "Elementos iniciais",
                "eyebrow": "Capa e folha de rosto",
                "description": "Informe os dados usados na capa, folha de rosto e folha de aprovação.",
                "tip": "O título deve comunicar tema e recorte com precisão. Evite títulos genéricos, slogans e abreviações não explicadas.",
                "checklist": [
                    "Nome do autor está completo e sem abreviações?",
                    "Título e subtítulo representam o recorte real?",
                    "Orientador, local e ano estão corretos?",
                ],
                "fields": [
                    field("author_name", "Nome completo do autor", rows=2, kind="text"),
                    field("title", "Título da monografia", rows=3),
                    field("subtitle", "Subtítulo", rows=2, placeholder="Opcional"),
                    field("advisor_title", "Título do orientador", rows=2, kind="text", placeholder="Ex.: Rev., Prof. Dr."),
                    field("advisor_name", "Nome do orientador", rows=2, kind="text"),
                    field("city", "Cidade — UF", rows=2, kind="text"),
                    field("year", "Ano", rows=2, kind="number"),
                    field("nature_text", "Natureza do trabalho", rows=5),
                ],
            },
        ),
        (
            "aprovacao",
            {
                "label": "Folha de aprovação",
                "short_label": "Aprovação",
                "group": "Elementos iniciais",
                "eyebrow": "Dados da banca",
                "description": "Preencha os dados conhecidos. Campos ainda indefinidos podem permanecer vazios no rascunho.",
                "tip": "Confirme grafia, titulação e instituição de cada examinador antes da entrega definitiva.",
                "checklist": ["Data corresponde à defesa?", "Titulações e instituições foram confirmadas?"],
                "fields": [
                    field("approval_date", "Data da aprovação", rows=2, kind="date"),
                    field("examiner_internal_title", "Título do examinador interno", rows=2, kind="text"),
                    field("examiner_internal_name", "Examinador interno", rows=2, kind="text"),
                    field("examiner_internal_institution", "Instituição do examinador interno", rows=2, kind="text"),
                    field("examiner_external_title", "Título do examinador externo", rows=2, kind="text"),
                    field("examiner_external_name", "Examinador externo", rows=2, kind="text"),
                    field("examiner_external_institution", "Instituição do examinador externo", rows=2, kind="text"),
                ],
            },
        ),
        (
            "dedicatoria",
            {
                "label": "Dedicatória",
                "short_label": "Dedicatória",
                "group": "Elementos opcionais",
                "eyebrow": "Elemento opcional",
                "description": "Homenagem breve a uma ou mais pessoas.",
                "tip": "Use linguagem pessoal e concisa. Não é necessário inserir o título “Dedicatória” no documento final.",
                "checklist": ["O texto está breve?", "Nomes próprios foram conferidos?"],
                "fields": [field("dedication", "Texto da dedicatória", rows=7)],
            },
        ),
        (
            "agradecimentos",
            {
                "label": "Agradecimentos",
                "short_label": "Agradecimentos",
                "group": "Elementos opcionais",
                "eyebrow": "Elemento opcional",
                "description": "Reconheça pessoas e instituições que contribuíram de modo relevante.",
                "tip": "Dê preferência a contribuições concretas: orientação, leitura, apoio institucional, pastoral ou familiar.",
                "checklist": ["Todas as pessoas citadas autorizaram a forma do nome?", "O tom é sóbrio e pessoal?"],
                "fields": [field("acknowledgements", "Texto dos agradecimentos", rows=10)],
            },
        ),
        (
            "epigrafe",
            {
                "label": "Epígrafe",
                "short_label": "Epígrafe",
                "group": "Elementos opcionais",
                "eyebrow": "Elemento opcional",
                "description": "Citação breve relacionada ao tema, acompanhada da autoria ou referência.",
                "tip": "Transcreva fielmente e registre a fonte na lista de referências quando aplicável.",
                "checklist": ["A citação foi conferida na fonte?", "A autoria está indicada?"],
                "fields": [
                    field("epigraph_text", "Texto da epígrafe", rows=5),
                    field("epigraph_author", "Autoria ou referência", rows=2, kind="text"),
                ],
            },
        ),
        (
            "base-confessional",
            {
                "label": "Base confessional",
                "short_label": "Base confessional",
                "group": "Elementos pré-textuais",
                "eyebrow": "Identidade acadêmica do SPN",
                "description": "Apresente a base confessional pertinente ao objeto, como ocorre no padrão institucional analisado.",
                "tip": "Escolha trechos realmente ligados ao problema. Diferencie com clareza a transcrição confessional de sua interpretação.",
                "checklist": ["O trecho dialoga com o problema de pesquisa?", "Documento, capítulo e seção foram identificados?", "A transcrição é fiel?"],
                "fields": [
                    field("confessional_title", "Documento confessional", rows=2, kind="text"),
                    field("confessional_subtitle", "Capítulo, seção ou assunto", rows=2, kind="text"),
                    field("confessional_content", "Trecho ou síntese confessional", rows=12),
                    field("confessional_references", "Referências bíblicas e documentais", rows=5),
                ],
            },
        ),
        (
            "resumo",
            {
                "label": "Resumo e palavras-chave",
                "short_label": "Resumo",
                "group": "Elementos pré-textuais",
                "eyebrow": "ABNT NBR 6028:2021",
                "description": "Sintetize problema, objetivo, método, resultados e conclusão em um único parágrafo.",
                "tip": "Escreva o resumo por último. Prefira terceira pessoa, voz ativa e frases informativas; não inclua citações ou tópicos.",
                "checklist": ["Problema e objetivo aparecem?", "Método e percurso estão claros?", "Resultado central e conclusão aparecem?", "Palavras-chave representam o conteúdo?"],
                "fields": [
                    field("abstract_pt", "Resumo", rows=12, placeholder="Parágrafo único, conciso e informativo."),
                    field("keywords_pt", "Palavras-chave", rows=2, kind="text", placeholder="Termo 1; Termo 2; Termo 3."),
                ],
            },
        ),
        (
            "abstract",
            {
                "label": "Abstract e keywords",
                "short_label": "Abstract",
                "group": "Elementos pré-textuais",
                "eyebrow": "Versão em língua inglesa",
                "description": "Apresente uma tradução fiel do resumo e das palavras-chave.",
                "tip": "Faça a tradução somente após estabilizar o resumo em português. A IA pode propor uma versão, mas nomes técnicos devem ser conferidos.",
                "checklist": ["O conteúdo corresponde ao resumo?", "Termos teológicos foram traduzidos de modo consistente?"],
                "fields": [
                    field("abstract_en", "Abstract", rows=12),
                    field("keywords_en", "Keywords", rows=2, kind="text", placeholder="Term 1; Term 2; Term 3."),
                ],
            },
        ),
        (
            "listas",
            {
                "label": "Listas",
                "short_label": "Listas",
                "group": "Elementos pré-textuais",
                "eyebrow": "Elementos condicionais",
                "description": "Cadastre abreviaturas e símbolos efetivamente utilizados no texto.",
                "tip": "Digite um item por linha no formato “SPN — Seminário Presbiteriano do Norte”. O sumário será criado automaticamente no DOCX.",
                "checklist": ["Todas as siglas não usuais foram explicadas?", "Os itens estão em ordem alfabética?"],
                "fields": [
                    field("abbreviations", "Lista de abreviaturas e siglas", rows=8),
                    field("symbols", "Lista de símbolos", rows=6),
                ],
            },
        ),
        (
            "introducao",
            {
                "label": "Introdução",
                "short_label": "Introdução",
                "group": "Texto",
                "eyebrow": "Abertura da argumentação",
                "description": "Conduza o leitor do contexto ao problema e apresente o percurso da pesquisa.",
                "tip": "Inclua contexto, delimitação, problema, hipótese quando houver, objetivos, justificativa, metodologia e mapa das seções — sem antecipar toda a conclusão.",
                "checklist": ["O leitor entende exatamente o problema?", "Objetivos e método correspondem ao projeto?", "A organização das seções foi anunciada?"],
                "fields": [field("introduction", "Texto da introdução", rows=22)],
            },
        ),
        (
            "desenvolvimento",
            {
                "label": "Desenvolvimento",
                "short_label": "Desenvolvimento",
                "group": "Texto",
                "eyebrow": "Seções e subseções",
                "description": "Construa a resposta ao problema em seções numeradas, com progressão argumentativa.",
                "tip": "O padrão observado no SPN combina três eixos úteis: contexto histórico; fundamento bíblico-teológico e confessional; implicações pastorais ou contemporâneas. Adapte-os ao seu problema, sem tratá-los como fórmula rígida.",
                "checklist": ["Cada seção cumpre um objetivo específico?", "Afirmações relevantes estão fundamentadas?", "Fontes são analisadas, e não apenas acumuladas?", "Há transições entre as seções?"],
                "fields": [],
                "dynamic": True,
            },
        ),
        (
            "consideracoes-finais",
            {
                "label": "Considerações finais",
                "short_label": "Considerações finais",
                "group": "Texto",
                "eyebrow": "Síntese e resposta",
                "description": "Responda ao problema com base no que foi demonstrado e registre os limites do estudo.",
                "tip": "Retome objetivos e achados sem copiar a introdução. Não introduza argumentos ou fontes essenciais que não foram discutidos no desenvolvimento.",
                "checklist": ["O problema recebeu uma resposta explícita?", "Os objetivos foram avaliados?", "Limitações e desdobramentos aparecem?"],
                "fields": [field("conclusion", "Texto das considerações finais", rows=20)],
            },
        ),
        (
            "pesquisa",
            {
                "label": "Pesquisa bibliográfica",
                "short_label": "Pesquisa",
                "group": "Fontes",
                "eyebrow": "Publicações reais e rastreáveis",
                "description": "Localize obras clássicas e recentes em catálogos acadêmicos e salve apenas o que conferir.",
                "tip": "Leia a obra antes de citá-la. Um link real comprova a existência da publicação, mas não substitui a avaliação de pertinência nem o acesso ao texto integral.",
                "checklist": ["Título e autoria correspondem ao link?", "A obra contribui para o problema?", "Metadados foram conferidos na publicação?"],
                "fields": [],
                "template": "works/research.html",
            },
        ),
        (
            "referencias",
            {
                "label": "Referências",
                "short_label": "Referências",
                "group": "Fontes",
                "eyebrow": "ABNT NBR 6023:2025",
                "description": "Revise as publicações salvas e mantenha somente as fontes efetivamente citadas no texto.",
                "tip": "Importe sua lista ABNT em DOCX/PDF ou salve publicações pesquisadas. A biblioteca alimenta o botão “Incluir ref.” e a lista final, ordenada alfabeticamente e exportada em espaço simples.",
                "checklist": ["Toda citação possui referência correspondente?", "Toda referência foi citada?", "Dados editoriais foram conferidos?"],
                "fields": [],
                "template": "works/references.html",
            },
        ),
        (
            "pos-textuais",
            {
                "label": "Pós-textuais",
                "short_label": "Pós-textuais",
                "group": "Elementos finais",
                "eyebrow": "Elementos opcionais",
                "description": "Inclua glossário, apêndices produzidos pelo autor e anexos de terceiros somente quando necessários.",
                "tip": "Apêndice é elaborado pelo próprio autor; anexo é um documento não elaborado pelo autor. Identifique cada item com letra e título.",
                "checklist": ["Cada item é mencionado no texto?", "A distinção entre apêndice e anexo está correta?"],
                "fields": [
                    field("glossary", "Glossário", rows=7, placeholder="Um verbete por linha."),
                    field("appendices", "Apêndices", rows=10),
                    field("annexes", "Anexos", rows=10),
                ],
            },
        ),
        (
            "exportar",
            {
                "label": "Revisar e exportar",
                "short_label": "Exportar DOCX",
                "group": "Finalização",
                "eyebrow": "Documento final",
                "description": "Faça a verificação final e gere a monografia editável em DOCX.",
                "tip": "Após abrir o arquivo no Word ou LibreOffice, atualize o sumário automático e confira paginação, quebras, citações e referências antes de entregar.",
                "checklist": ["Dados institucionais e banca estão corretos?", "Sumário foi atualizado no editor de texto?", "Citações e referências foram cruzadas?", "Versão final foi revisada por uma pessoa?"],
                "fields": [],
                "template": "works/export.html",
            },
        ),
    ]
)


GROUPS = []
for slug, config in PARTS.items():
    if not GROUPS or GROUPS[-1]["label"] != config["group"]:
        GROUPS.append({"label": config["group"], "items": []})
    GROUPS[-1]["items"].append({"slug": slug, **config})


EDITABLE_FIELDS = {
    item["name"]
    for part in PARTS.values()
    for item in part.get("fields", [])
}


AI_FIELDS = {
    item["name"]
    for part in PARTS.values()
    for item in part.get("fields", [])
    if item["kind"] == "textarea"
}


# Campos que realmente entram no texto acadêmico exportado e nos quais notas
# referenciais são apropriadas. Resumo, dedicatória, epígrafe e formulário de
# planejamento permanecem sem notas por orientação metodológica.
CITATION_FIELDS = {
    "acknowledgements",
    "confessional_content",
    "confessional_references",
    "introduction",
    "conclusion",
    "glossary",
    "appendices",
    "annexes",
}


ONBOARDING_SLIDES = [
    {
        "number": "01",
        "title": "Parta de uma pergunta possível",
        "text": "Delimite o tema, formule o problema e alinhe objetivos e método antes de redigir a introdução.",
        "tag": "Planejamento",
    },
    {
        "number": "02",
        "title": "Construa uma linha de argumentação",
        "text": "Organize o desenvolvimento em seções. Contexto histórico, fundamento bíblico-teológico/confessional e implicações pastorais formam um percurso recorrente no SPN.",
        "tag": "Estrutura",
    },
    {
        "number": "03",
        "title": "Distinga sua voz das fontes",
        "text": "Apresente, interprete e dialogue com cada autor. Identifique toda citação e nunca use uma referência que não tenha conferido.",
        "tag": "Integridade",
    },
    {
        "number": "04",
        "title": "Use a IA como revisora",
        "text": "A IA sugere clareza, coesão e registro acadêmico, mas não substitui autoria, pesquisa, discernimento teológico ou verificação das fontes.",
        "tag": "Revisão",
    },
    {
        "number": "05",
        "title": "Finalize segundo a ABNT",
        "text": "O DOCX aplica a estrutura do SPN e as normas atuais. Atualize o sumário e faça a conferência humana da versão final.",
        "tag": "Entrega",
    },
]
