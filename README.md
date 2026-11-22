# Legis Diff

Biblioteca e CLI open source para transformar textos legislativos brasileiros em árvores sintáticas e calcular diferenças **estruturais** e **semânticas** entre versões — por [Como Votam](https://comovotam.com.br).

Um `git diff` comum enxerga linhas. O Legis Diff enxerga artigos, parágrafos, incisos, alíneas, dispositivos inseridos, revogados, movimentados ou renumerados.

## Começar

```bash
python -m pip install uv
uv sync
uv run legisdiff --help
uv run legisdiff parse examples/mini_v1.txt -o /tmp/ast.json
uv run legisdiff diff examples/mini_v1.txt examples/mini_v2.txt -o /tmp/diff.json
uv run legisdiff patch examples/mini_v1.txt examples/mini_v2.txt
uv run legisdiff stats examples/mini_v1.txt
```

Use `uv run` em todos os comandos. Avaliação offline não exige chaves.

## O efeito

```bash
uv run legisdiff patch examples/mini_v1.txt examples/mini_v2.txt
```

Saída típica:

```
+ INSERT artigo art.3: Fica criado o comitê de acompanhamento.
# RENUMBER artigo art.3 → art.4
~ MODIFY caput art.1/caput (sim=86%)
+ INSERT inciso art.2/caput/inc.IV: publicidade.
```

O JSON correspondente lista cada operação com ids, paths, rótulos e similaridade.

## O que faz

1. **Parse** — técnica legislativa da LC 95/1998 (Parte → Item), HTML do Planalto e LexML XML.
2. **AST** — cada dispositivo ganha `id`/`path` estáveis (`art.10/p.1/inc.II/al.a`) e fingerprint de conteúdo.
3. **Match** — corresponde árvores mesmo com renumeração, usando fingerprint + similaridade.
4. **Diff** — `insert`, `delete`, `modify`, `move`, `renumber`, `revoke`.
5. **Patch** — relatório legível além do JSON.

## CLI

| Comando | Função |
|---------|--------|
| `legisdiff parse ARQ` | Texto/HTML/LexML → AST JSON |
| `legisdiff diff A B` | Diff estrutural JSON |
| `legisdiff patch A B` | Patch legível |
| `legisdiff explain diff.json` | Reimprime patch a partir do JSON |
| `legisdiff stats ARQ` | Contagem por tipo de dispositivo |

Detalhes em [docs/cli.md](docs/cli.md). Metodologia em [docs/metodologia.md](docs/metodologia.md). Estrutura da AST em [docs/estrutura.md](docs/estrutura.md).

## Biblioteca

```python
from legisdiff import parse_text, diff_texts
from legisdiff.patch import render_patch

doc = parse_text(open("lei.txt", encoding="utf-8").read())
report = diff_texts(old, new, old_source="v1", new_source="v2")
print(render_patch(report))
```

## Validação com documentos reais

```bash
uv run python scripts/fetch_samples.py
uv run python scripts/validate_manual.py
```

Baixa LC 95, Lei 8.666, Lei 14.133, Decreto 9.191, Constituição (compilada) e a versão do Senado; parseia e gera artefatos em `data/validation/`.

Valores observados na validação manual:

| Documento | Dispositivos | Artigos |
|-----------|-------------:|--------:|
| LC 95 (Planalto) | 156 | 23 |
| Decreto 9.191 | 468 | 71 |
| Lei 8.666 | 1.240 | 148 |
| Lei 14.133 | 1.804 | 216 |
| CF/88 compilada | 3.919 | 427 |

## Por que existe

O ecossistema LexML trata estrutura legislativa; o LexML ETA edita textos articulados. Faltava um **motor genérico de diff** que transforme versões heterogêneas em mudanças estruturais reutilizáveis (JSON + patch). Tree diffs genéricos (ex.: GumTree) não conhecem artigo/§/inciso nem renumeração legislativa.

## Organização

Inspirada no [Teor](https://github.com/comovotam/teor): pacote Python + Typer + Pydantic, contratos explícitos, CLI com artefatos, docs e scripts de reprodução. Sem site neste repositório.

## Limites

- Textos sem articulação (exposição de motivos corrida, pareceres narrativos) produzem AST rasa.
- PDFs precisam ser convertidos a texto/HTML antes.
- Similaridade é lexical; não interpreta intenção política.

Código sob Apache-2.0. Adriano Coelho / Como Votam mantêm o projeto.
