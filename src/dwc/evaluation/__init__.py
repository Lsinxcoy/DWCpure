"""DWC-AUTO · Fixed evaluation API; formal attempt selection stays in observability."""
from dwc.observability.task_metrics import select_formal_attempts

from .protocol import Protocol, Qualification, qualify_run

__all__ = ["Protocol", "Qualification", "qualify_run", "select_formal_attempts"]
