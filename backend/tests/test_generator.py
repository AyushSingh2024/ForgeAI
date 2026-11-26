"""Req 3: tool selection, retrieval rules, a round-tripping agent.yaml and the skeleton guarantees."""

from __future__ import annotations

from forge.config import load_config
from forge.generator import run_generate_agent
from forge.generator.retrieval_params import choose_retrieval
from forge.generator.tool_selector import select_tools
from forge.intake import run_intake
from forge.schemas.agent_def import load_agent
from forge.schemas.corpus import ColumnInfo, CorpusProfile, TableInfo
from forge.schemas.groundability import AskVerdict, GroundabilityReport
from forge.schemas.requirements import MustAnswer, Requirements
from tests.conftest import scripted
from tests.test_intake import DRAFT


def test_hr_like_brief_gets_no_csv_or_weather():
    req = Requirements(brief="Answer employee questions about leave and code of conduct policies.",
                       must_answer=[MustAnswer(id="a1", topic="sick leave rules")])
    names = [t.name for t in select_tools(req, None, CorpusProfile())]
    assert "csv_lookup" not in names and "http_weather" not in names


def test_spares_like_brief_gets_all_four():
    profile = CorpusProfile(tables=[TableInfo(name="spares_inventory", path="/x/input/docs/spares_inventory.csv",
                                              columns=[ColumnInfo(name="part_no", dtype="text")])])
    req = Requirements(brief="Find spare parts, estimate the total cost of an order, check the weather forecast at "
                             "the delivery port and say how many days until delivery.")
    guard = GroundabilityReport(verdicts=[AskVerdict(ask_id="b1", ask_text="port weather", verdict="needs_tool",
                                                     needed_tool="http_weather")])
    tools = {t.name: t for t in select_tools(req, guard, profile)}
    assert set(tools) == {"csv_lookup", "calculator", "http_weather", "current_date"}
    assert all(t.reason for t in tools.values())
    assert tools["csv_lookup"].config["tables"][0]["path"] == "docs/spares_inventory.csv"


def test_retrieval_rules():
    cfg = load_config(env={})
    assert choose_retrieval(CorpusProfile(median_section_tokens=120), cfg).chunk_size == 350
    assert choose_retrieval(CorpusProfile(median_section_tokens=1200), cfg).chunk_size == 700


def test_generated_agent_roundtrips_and_has_rules(make_fake_hub, make_run, cfg):
    hub = make_fake_hub(agent=scripted([("designing a question-answering assistant", DRAFT)]))
    ctx = make_run(hub)
    run_intake(ctx)
    agent = run_generate_agent(ctx)
    loaded = load_agent(ctx.path("agent", "agent.yaml"))
    assert loaded == agent
    assert "NON-NEGOTIABLE RULES" in agent.system_prompt.rendered
    assert "csv_lookup" in agent.tool_names()  # tiny corpus has classes.csv
    assert (ctx.path("agent", "index", "manifest.json")).exists()
