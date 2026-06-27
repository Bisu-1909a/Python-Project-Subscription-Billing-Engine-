"""
InvoiceRenderer — *** BONUS / OPTIONAL — NOT REQUIRED FOR THE CORE PROJECT ***

The core project uses a plain-text invoice format (see
`billing_engine.cli.format_invoice_text`). This PDF renderer is provided as a
**bonus exercise** for students who want to explore the `reportlab` library.

To attempt the bonus:
    1. Install reportlab:  `pip install reportlab`
    2. Implement the methods below.
    3. (Optional) wire `billing invoice show <id> --pdf` in cli.py.

NO tests cover this module — the bonus is graded by visual inspection of the
output PDF only.

Resource: https://www.reportlab.com/docs/reportlab-userguide.pdf
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from billing_engine.models import Customer, Invoice, InvoiceLineItem


class InvoiceRenderer:
    """BONUS — only implement if you want to explore PDF generation."""

    def __init__(self, output_dir: str | Path = "invoices") -> None:
        # BONUS — see module docstring.
        #   - Convert output_dir to Path.
        #   - Create the directory if it doesn't exist (mkdir parents=True, exist_ok=True).
        raise NotImplementedError("BONUS: implement InvoiceRenderer.__init__")

    def render(
        self,
        invoice: Invoice,
        customer: Customer,
        line_items: Iterable[InvoiceLineItem],
    ) -> Path:
        
        raise NotImplementedError("BONUS: implement InvoiceRenderer.render")
