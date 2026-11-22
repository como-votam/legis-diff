# Estrutura da AST e do diff

## Node

| Campo | Significado |
|-------|-------------|
| `kind` | `artigo`, `caput`, `paragrafo`, `inciso`, `alinea`, `item`, agrupadores, etc. |
| `label` | Número/rótulo canônico (`10`, `unico`, `II`, `a`) |
| `title` | Título de agrupador, se houver |
| `text` | Enunciado do dispositivo |
| `id` / `path` | Caminho estrutural |
| `fingerprint` | Hash do conteúdo normalizado |
| `revoked` | Marca de revogado/vetado |
| `notes` | Notas editoriais `(Incluído pela…)` |
| `children` | Filhos na árvore |

## Document

Metadados leves (`epigrafe`, `ementa`, `format`, `warnings`) + `root`.

## Change

| `op` | Significado |
|------|-------------|
| `insert` | Só na versão nova |
| `delete` | Só na versão antiga |
| `modify` | Mesmo dispositivo, texto diferente |
| `renumber` | Conteúdo correspondente, rótulo/path numerado mudou |
| `move` | Conteúdo correspondente, pai estrutural mudou |
| `revoke` | Passou a revogado/vetado |
| `equal` | Inalterado (omitido por padrão) |

## Schemas

Exporte o schema Pydantic se precisar de contrato formal:

```bash
uv run python -c "from legisdiff.models import DiffReport, Document; \
import json; \
print(json.dumps(DiffReport.model_json_schema(), ensure_ascii=False, indent=2))"
```
