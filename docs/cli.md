# CLI

O executável `legisdiff` é registrado pelo pacote `comovotam-legisdiff`.

```bash
uv sync
uv run legisdiff --help
uv run legisdiff --version
```

## parse

```bash
uv run legisdiff parse lei.txt -o ast.json
uv run legisdiff parse lei.html -o ast.json
uv run legisdiff parse norma.xml --indent
```

Detecta `.txt`, `.html`/`.htm` e `.xml`/LexML. Avisos de linhas órfãs vão para stderr.

## diff

```bash
uv run legisdiff diff v1.txt v2.txt -o diff.json
uv run legisdiff diff v1.txt v2.txt --include-equal --threshold 0.6
```

`--threshold` (0–1) controla o limiar mínimo para parear dispositivos como `modify` em vez de delete+insert.

## patch

```bash
uv run legisdiff patch v1.txt v2.txt
uv run legisdiff patch v1.txt v2.txt -o mudancas.patch.txt
```

## explain

```bash
uv run legisdiff explain diff.json
```

## stats

```bash
uv run legisdiff stats data/raw/lc95.html
```

## Artefatos

JSON é canônico (`sort_keys`, UTF-8, newline final). Escrita atômica (temp + replace), no mesmo espírito do Teor.
