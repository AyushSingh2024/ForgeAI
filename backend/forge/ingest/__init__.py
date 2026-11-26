"""Turn a folder of files into Documents, Chunks, Tables and a CorpusProfile (stage "ingest")."""

from forge.ingest.profiler import run_ingest

__all__ = ["run_ingest"]
