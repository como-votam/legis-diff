"""Contratos do Legis Diff: AST, dispositivos e relatório de mudanças."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

NodeKind = Literal[
    "documento",
    "epigrafe",
    "ementa",
    "preambulo",
    "parte",
    "livro",
    "titulo",
    "capitulo",
    "secao",
    "subsecao",
    "agrupamento",
    "artigo",
    "caput",
    "paragrafo",
    "inciso",
    "alinea",
    "item",
    "fechamento",
    "anexo",
    "texto",
]

ChangeOp = Literal[
    "equal",
    "insert",
    "delete",
    "modify",
    "move",
    "renumber",
    "revoke",
]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["1.0"] = "1.0"


class Node(Contract):
    """Nó da árvore sintática legislativa."""

    kind: NodeKind
    label: str | None = None
    title: str | None = None
    text: str = ""
    id: str = ""
    path: str = ""
    fingerprint: str = ""
    revoked: bool = False
    notes: list[str] = Field(default_factory=list)
    children: list[Node] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)

    def iter_devices(self) -> list[Node]:
        """Dispositivos relevantes para diff (exclui o documento raiz)."""
        out: list[Node] = []
        if self.kind != "documento":
            out.append(self)
        for child in self.children:
            out.extend(child.iter_devices())
        return out

    def find(self, node_id: str) -> Node | None:
        if self.id == node_id:
            return self
        for child in self.children:
            found = child.find(node_id)
            if found is not None:
                return found
        return None


class Document(Contract):
    """Documento legislativo parseado."""

    source: str | None = None
    format: Literal["text", "html", "lexml"] = "text"
    epigrafe: str | None = None
    ementa: str | None = None
    root: Node
    warnings: list[str] = Field(default_factory=list)

    @property
    def devices(self) -> list[Node]:
        return self.root.iter_devices()


class TextSpan(Contract):
    before: str
    after: str
    similarity: float = Field(ge=0, le=1)


class Change(Contract):
    op: ChangeOp
    kind: NodeKind | None = None
    old_id: str | None = None
    new_id: str | None = None
    old_path: str | None = None
    new_path: str | None = None
    old_label: str | None = None
    new_label: str | None = None
    old_text: str | None = None
    new_text: str | None = None
    similarity: float | None = Field(default=None, ge=0, le=1)
    reason: str | None = None
    text_diff: TextSpan | None = None


class DiffSummary(Contract):
    equal: int = 0
    insert: int = 0
    delete: int = 0
    modify: int = 0
    move: int = 0
    renumber: int = 0
    revoke: int = 0
    devices_old: int = 0
    devices_new: int = 0


class DiffReport(Contract):
    summary: DiffSummary
    changes: list[Change] = Field(default_factory=list)
    old_source: str | None = None
    new_source: str | None = None
    options: dict[str, Any] = Field(default_factory=dict)

    @property
    def meaningful(self) -> list[Change]:
        return [c for c in self.changes if c.op != "equal"]
