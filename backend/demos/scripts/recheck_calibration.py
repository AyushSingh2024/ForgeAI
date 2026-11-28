"""Re-run ONLY the judge calibration of a finished run with the current probes and judge prompt.

It never touches the run's own artifacts: the result goes to a separate JSON file, so the committed run stays exactly
as it was graded. Only a local Ollama judge is allowed, so this costs nothing and sends nothing to a hosted API.

    python demos/scripts/recheck_calibration.py demos/hr_policy/run demos/hr_policy/run/judge_calibration_recheck.json
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND))

from forge.config import load_config, with_overrides
from forge.judge.calibration import run_calibration
from forge.judge.pairwise import flip_agreement
from forge.llm.client import make_hub
from forge.llm.prompts import load_prompt
from forge.schemas.corpus import Chunk
from forge.schemas.eval_case import EvalCase
from forge.schemas.requirements import Requirements
from forge.util import read_json, read_jsonl, write_json


def main(run_dir: Path, out: Path) -> None:
    cfg = load_config()
    if cfg.llm.judge_provider != "ollama":
        raise SystemExit("this script only runs with a local Ollama judge (JUDGE_PROVIDER=ollama)")
    # the agent and builder are never called here; point them at Ollama too so no hosted client is even created
    cfg = with_overrides(cfg, "llm", agent_provider="ollama", agent_model=cfg.llm.judge_model, use_cache=False)
    hub = make_hub(cfg)
    ok, msg = hub.judge.health()
    if not ok:
        raise SystemExit(f"local judge not reachable: {msg}")
    req = Requirements.model_validate(read_json(run_dir / "requirements.json"))
    cases = read_jsonl(run_dir / "evals" / "cases.jsonl", EvalCase)
    chunks = {c.chunk_id: c for c in read_jsonl(run_dir / "corpus" / "chunks.jsonl", Chunk)}
    tone = f"{req.tone.style} (formality {req.tone.formality}) for {req.audience.who}"
    info, pairs = run_calibration(cases, chunks, hub.judge, tone)
    original = read_json(run_dir / "judge_calibration.json", {})
    prompt = load_prompt("judge_rubric")
    write_json(out, {
        "run": str(run_dir.as_posix()), "judge": hub.judge.model_id,
        "checked_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "judge_rubric_version": prompt.version,
        "original": {k: original.get(k) for k in ("calibration_pass", "calibration_passed", "calibration_total")},
        "recheck": {**info, "flip_agreement": flip_agreement(pairs)},
    })
    print(f"{run_dir.as_posix()}: original {original.get('calibration_passed')}/{original.get('calibration_total')} -> "
          f"recheck {info['calibration_passed']}/{info['calibration_total']} "
          f"({'trusted' if info['calibration_pass'] else 'NOT trusted'}) with {hub.judge.model_id}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    main(Path(sys.argv[1]), Path(sys.argv[2]))
