"""Legis Diff — AST e diff estrutural de textos legislativos brasileiros."""

from legisdiff.diff import diff_documents, diff_texts
from legisdiff.models import Change, DiffReport, Document, Node
from legisdiff.parser import parse_text

__version__ = "1.0.0"
__all__ = [
    "Change",
    "DiffReport",
    "Document",
    "Node",
    "diff_documents",
    "diff_texts",
    "parse_text",
]
