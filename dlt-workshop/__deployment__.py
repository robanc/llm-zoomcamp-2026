"""Deploy the hosted agent-traces REST API pipeline and dashboard."""

import sys
from pathlib import Path

CODE_DIR = Path(__file__).parent / "code"
sys.path.insert(0, str(CODE_DIR))

from rest_api_pipeline import ingest_agent_traces
import agent_traces_dashboard

__all__ = [
    "ingest_agent_traces",
    "agent_traces_dashboard",
]