# Metodologia

## Problema

Comparar duas versões de uma norma com diff textual confunde:

- inserção de um artigo no meio (tudo “desloca” nas linhas);
- renumeração sem mudança de conteúdo;
- revogação explícita (“(Revogado)”);
- movimentação de inciso entre caput e parágrafo.

O Legis Diff modela o texto como árvore de dispositivos e compara nós, não linhas.

## Hierarquia (LC 95/1998)

```
Parte → Livro → Título → Capítulo → Seção → Subseção
  └─ Artigo
       ├─ Caput
       │    ├─ Inciso → Alínea → Item
       └─ Parágrafo
            └─ Inciso → Alínea → Item
```

Agrupamentos nomeados (`DISPOSIÇÕES PRELIMINARES`, `Da Articulação…`) entram como `agrupamento`.

## Identificadores

Cada nó recebe:

- `path` / `id` estrutural: `art.5/p.1/inc.II/al.a`
- `fingerprint`: hash do texto normalizado (sem acento, minúsculas, espaços colapsados)

Artigos com letra (`Art. 5º-A`) viram `art.5-A`.

## Correspondência

Quatro fases:

1. **Fingerprint único** nos dois lados → equal / renumber / move
2. **Mesmo path** → equal ou modify
3. **Similaridade por tipo** (Jaccard + SequenceMatcher) → modify / renumber / move
4. **Restantes** → insert / delete

`renumber` = mesmo conteúdo (ou quase), path mudou só no rótulo/ancestral numerado.  
`move` = conteúdo correspondente sob pai estrutural diferente.  
`revoke` = dispositivo passa a carregar marca de revogado/vetado.

## Saídas

- **JSON** (`DiffReport`): máquina, estável, com summary e lista de `Change`
- **Patch**: humano, glifos `+ - ~ # > x`

## Fontes de entrada

| Formato | Caminho |
|---------|---------|
| Texto articulado `.txt` | parser LC 95 |
| HTML Planalto/Casa Civil | `html_to_text` → parser |
| LexML XML | mapeamento de tags → AST |

## Não objetivos

- Não é editor (vide LexML ETA).
- Não classifica mérito político.
- Não substitui consolidação oficial.
