"""The four tools."""

from __future__ import annotations

import httpx

from forge.runtime.tools.calculator import CalculatorTool
from forge.runtime.tools.csv_lookup import CsvLookupTool
from forge.runtime.tools.current_date import CurrentDateTool
from forge.runtime.tools.http_weather import WeatherTool


def test_calculator_maths_and_safety():
    calc = CalculatorTool()
    assert calc.run({"expression": "12 * 345.5"}).data["result"] == 4146.0
    assert calc.run({"expression": "min(3, 2) + 1,200"}).data["result"] == 1202
    for bad in ["__import__('os').system('x')", "a + 1", "2 ** 999", "().__class__"]:
        assert not calc.run({"expression": bad}).ok


def test_csv_lookup(tiny_corpus):
    tool = CsvLookupTool(config={"tables": [{"name": "classes", "path": str(tiny_corpus / "classes.csv")}]})
    r = tool.run({"table": "classes", "filters": [{"column": "name", "op": "eq", "value": "spin"}]})
    assert r.ok and r.data["row_count"] == 3
    r = tool.run({"table": "classes", "aggregate": {"op": "sum", "column": "capacity"},
                  "filters": [{"column": "weekday", "op": "eq", "value": "Saturday"}]})
    assert r.data["value"] == 30
    bad = tool.run({"table": "classes", "filters": [{"column": "colour", "op": "eq", "value": 1}]})
    assert not bad.ok and "Valid columns" in bad.error
    assert not tool.run({"table": "secrets"}).ok


def test_current_date(fixed_date):
    r = CurrentDateTool().run({"offset_days": 45})
    assert r.data["date"] == "2026-03-01"


def test_weather_with_mock():
    def handler(request: httpx.Request):
        if "geocoding" in request.url.host:
            return httpx.Response(200, json={"results": [{"name": "Rotterdam", "country": "Netherlands",
                                                          "latitude": 51.9, "longitude": 4.5}]})
        return httpx.Response(200, json={"daily": {"time": ["2026-01-15"], "temperature_2m_max": [7.0],
                                                   "temperature_2m_min": [2.0], "precipitation_sum": [1.2],
                                                   "wind_speed_10m_max": [30.0]}})

    tool = WeatherTool(client=httpx.Client(transport=httpx.MockTransport(handler)))
    r = tool.run({"location": "Rotterdam", "days": 1})
    assert r.ok and r.data["place"] == "Rotterdam, Netherlands" and r.data["daily"][0]["wind_max_kmh"] == 30.0
    assert not WeatherTool().run({}).ok  # no place given
