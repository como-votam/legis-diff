"""CLI legisdiff — parse, diff e patch de textos legislativos."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from legisdiff import __version__
from legisdiff.diff import diff_documents
from legisdiff.io import dump_document, dump_report, load_document, write_json, write_text
from legisdiff.models import DiffReport
from legisdiff.patch import render_patch

app = typer.Typer(
    help="Legis Diff — AST e diff estrutural de textos legislativos brasileiros",
    no_args_is_help=True,
)


def _print_summary(report: DiffReport) -> None:
    s = report.summary
    typer.echo(
        f"+{s.insert} -{s.delete} ~{s.modify} #{s.renumber} >{s.move} x{s.revoke} "
        f"(={s.equal}; {s.devices_old}→{s.devices_new} dispositivos)"
    )


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: Annotated[
        bool,
        typer.Option("--version", help="Mostra a versão e sai"),
    ] = False,
) -> None:
    if version:
        typer.echo(__version__)
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()


@app.command("parse")
def parse_cmd(
    source: Path = typer.Argument(..., exists=True, readable=True, help="Arquivo .txt/.html/.xml"),
    output: Annotated[
        Path | None,
        typer.Option("-o", "--output", help="JSON da AST (stdout se omitido)"),
    ] = None,
    indent: Annotated[bool, typer.Option(help="JSON indentado")] = False,
) -> None:
    """Converte um texto legislativo em AST JSON."""
    doc = load_document(source)
    payload = dump_document(doc)
    if output:
        write_json(output, payload)
        typer.echo(
            f"AST: {len(doc.devices)} dispositivos → {output}"
            + (f" ({len(doc.warnings)} avisos)" if doc.warnings else "")
        )
    else:
        import json

        typer.echo(
            json.dumps(payload, ensure_ascii=False, indent=2 if indent else None, sort_keys=True)
        )
    for warning in doc.warnings:
        typer.secho(f"aviso: {warning}", fg=typer.colors.YELLOW, err=True)


@app.command("diff")
def diff_cmd(
    old: Path = typer.Argument(..., exists=True, readable=True),
    new: Path = typer.Argument(..., exists=True, readable=True),
    output: Annotated[
        Path | None,
        typer.Option("-o", "--output", help="JSON do diff"),
    ] = None,
    include_equal: Annotated[
        bool, typer.Option("--include-equal", help="Inclui dispositivos inalterados")
    ] = False,
    threshold: Annotated[
        float,
        typer.Option("--threshold", min=0.0, max=1.0, help="Limiar de similaridade para modify"),
    ] = 0.55,
) -> None:
    """Compara duas versões e emite JSON estruturado de mudanças."""
    old_doc = load_document(old)
    new_doc = load_document(new)
    report = diff_documents(
        old_doc,
        new_doc,
        include_equal=include_equal,
        modify_threshold=threshold,
    )
    payload = dump_report(report)
    if output:
        write_json(output, payload)
        typer.echo(f"Diff → {output}")
    else:
        import json

        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    _print_summary(report)


@app.command("patch")
def patch_cmd(
    old: Path = typer.Argument(..., exists=True, readable=True),
    new: Path = typer.Argument(..., exists=True, readable=True),
    output: Annotated[
        Path | None,
        typer.Option("-o", "--output", help="Arquivo de patch legível"),
    ] = None,
    threshold: Annotated[float, typer.Option("--threshold", min=0.0, max=1.0)] = 0.55,
) -> None:
    """Gera patch legível (dispositivos inseridos, removidos, movidos, etc.)."""
    report = diff_documents(
        load_document(old),
        load_document(new),
        modify_threshold=threshold,
    )
    text = render_patch(report)
    if output:
        write_text(output, text)
        typer.echo(f"Patch → {output}")
    else:
        typer.echo(text, nl=False)
    _print_summary(report)


@app.command("explain")
def explain_cmd(
    report_json: Path = typer.Argument(..., exists=True, readable=True, help="Diff JSON"),
) -> None:
    """Reimprime um diff JSON como patch legível."""
    from legisdiff.io import read_json
    from legisdiff.models import DiffReport

    report = DiffReport.model_validate(read_json(report_json))
    typer.echo(render_patch(report), nl=False)
    _print_summary(report)


@app.command("stats")
def stats_cmd(
    source: Path = typer.Argument(..., exists=True, readable=True),
) -> None:
    """Conta dispositivos por tipo em um documento."""
    from collections import Counter

    doc = load_document(source)
    counts = Counter(d.kind for d in doc.devices)
    typer.echo(f"fonte: {source}")
    if doc.epigrafe:
        typer.echo(f"epígrafe: {doc.epigrafe}")
    if doc.ementa:
        typer.echo(f"ementa: {doc.ementa[:120]}{'…' if len(doc.ementa) > 120 else ''}")
    typer.echo(f"total: {len(doc.devices)} dispositivos")
    for kind, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        typer.echo(f"  {kind}: {n}")
    for warning in doc.warnings:
        typer.secho(f"aviso: {warning}", fg=typer.colors.YELLOW, err=True)


if __name__ == "__main__":
    app()
