"""
models/agent_tools/api_client.py
Thin HTTP client that wraps every FastAPI endpoint as a Python method.
The AccidentAgent calls these methods after Ollama picks a tool.
"""

import requests
import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


class AccidentAPIClient:
    """
    Wraps every accident-data API endpoint as a plain Python method.
    All methods return raw Python objects (list/dict) ready to be
    JSON-serialised back into the Ollama tool-call loop.
    """

    def __init__(self, base_url: str = "http://localhost:8001"):
        self.base = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})

    # ── Internal helper ───────────────────────────────────────────────────────

    def _get(self, path: str, params: Optional[Dict] = None) -> Any:
        clean = {k: v for k, v in (params or {}).items() if v is not None}
        try:
            resp = self.session.get(f"{self.base}{path}", params=clean, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.ConnectionError:
            return {"error": f"Cannot connect to Data API at {self.base}. "
                             "Is `uvicorn accident_api.main:app --port 8001` running?"}
        except requests.exceptions.HTTPError as exc:
            return {"error": f"API error {exc.response.status_code}: "
                             f"{exc.response.text[:200]}"}
        except Exception as exc:
            logger.error("API client error: %s", exc)
            return {"error": str(exc)}

    # ── Tool methods (called by AccidentAgent.dispatch) ───────────────────────

    def list_cities(self, dataset: Optional[str] = None) -> Any:
        return self._get("/cities", {"dataset": dataset})

    def list_datasets(self) -> Any:
        return self._get("/datasets")

    def query_road_features(
        self,
        year: int,
        city: Optional[str] = None,
        sort_by: Optional[str] = None,
        top_n: Optional[int] = None,
        ascending: bool = True,
    ) -> Any:
        return self._get(f"/road-features/{year}",
                         {"city": city, "sort_by": sort_by,
                          "top_n": top_n, "ascending": ascending})

    def query_road_features_summary(self, year: int) -> Any:
        return self._get(f"/road-features/{year}/summary")

    def query_junctions(
        self,
        year: int,
        city: Optional[str] = None,
        sort_by: Optional[str] = None,
        top_n: Optional[int] = None,
        ascending: bool = True,
    ) -> Any:
        return self._get(f"/junctions/{year}",
                         {"city": city, "sort_by": sort_by,
                          "top_n": top_n, "ascending": ascending})

    def query_junctions_summary(self, year: int) -> Any:
        return self._get(f"/junctions/{year}/summary")

    def query_traffic_control(
        self,
        year: int,
        city: Optional[str] = None,
        sort_by: Optional[str] = None,
        top_n: Optional[int] = None,
        ascending: bool = True,
    ) -> Any:
        return self._get(f"/traffic-control/{year}",
                         {"city": city, "sort_by": sort_by,
                          "top_n": top_n, "ascending": ascending})

    def query_traffic_control_summary(self, year: int) -> Any:
        return self._get(f"/traffic-control/{year}/summary")

    def query_traffic_violations(
        self,
        year: int,
        city: Optional[str] = None,
        sort_by: Optional[str] = None,
        top_n: Optional[int] = None,
        ascending: bool = True,
    ) -> Any:
        return self._get(f"/traffic-violations/{year}",
                         {"city": city, "sort_by": sort_by,
                          "top_n": top_n, "ascending": ascending})

    def query_traffic_violations_summary(self, year: int) -> Any:
        return self._get(f"/traffic-violations/{year}/summary")

    def query_weather(
        self,
        year: int,
        city: Optional[str] = None,
        sort_by: Optional[str] = None,
        top_n: Optional[int] = None,
        ascending: bool = True,
    ) -> Any:
        return self._get(f"/weather/{year}",
                         {"city": city, "sort_by": sort_by,
                          "top_n": top_n, "ascending": ascending})

    def query_weather_summary(self, year: int) -> Any:
        return self._get(f"/weather/{year}/summary")

    def query_vehicles(
        self,
        city: Optional[str] = None,
        sort_by: Optional[str] = None,
        top_n: Optional[int] = None,
        ascending: bool = True,
    ) -> Any:
        return self._get("/vehicles/2020",
                         {"city": city, "sort_by": sort_by,
                          "top_n": top_n, "ascending": ascending})

    def query_vehicles_summary(self) -> Any:
        return self._get("/vehicles/2020/summary")

    def query_road_defects(
        self,
        state: Optional[str] = None,
        year: Optional[int] = None,
        sort_by: Optional[str] = None,
        top_n: Optional[int] = None,
        ascending: bool = True,
    ) -> Any:
        return self._get("/road-defects/",
                         {"state": state, "year": year,
                          "sort_by": sort_by, "top_n": top_n,
                          "ascending": ascending})

    def query_road_defects_summary(self) -> Any:
        return self._get("/road-defects/summary")

    def compare_years(
        self,
        category: str,
        years: List[int],
        city: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Call the same category endpoint for each year and return a dict of
        {year: data}.  category must be one of:
        road_features | junctions | traffic_control |
        traffic_violations | weather | vehicles
        """
        method_map = {
            "road_features":      self.query_road_features,
            "junctions":          self.query_junctions,
            "traffic_control":    self.query_traffic_control,
            "traffic_violations": self.query_traffic_violations,
            "weather":            self.query_weather,
            "vehicles":           lambda year, **kw: self.query_vehicles(**kw),
        }
        fn = method_map.get(category)
        if fn is None:
            return {"error": f"Unknown category '{category}'. "
                             "Choose from: " + ", ".join(method_map)}
        results = {}
        for year in years:
            try:
                results[str(year)] = fn(year=year, city=city)
            except TypeError:
                results[str(year)] = fn(city=city)
        return results

    # ── Dispatch ──────────────────────────────────────────────────────────────

    def dispatch(self, tool_name: str, args: Dict) -> Any:
        method = getattr(self, tool_name, None)
        if method is None:
            return {"error": f"Unknown tool '{tool_name}'"}
        try:
            return method(**args)
        except TypeError as exc:
            return {"error": f"Bad arguments for tool '{tool_name}': {exc}"}
        except Exception as exc:
            logger.error("Dispatch error for %s: %s", tool_name, exc)
            return {"error": str(exc)}
