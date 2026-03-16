"""
models/agent_tools/tool_definitions.py
Ollama-compatible tool schemas for every accident-data API endpoint.
The AccidentAgent passes this list directly to ollama.chat(tools=...).
"""

TOOLS = [
    # ── Meta ─────────────────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "list_cities",
            "description": (
                "Return all city names available in the accident datasets. "
                "Optionally filter to a specific dataset key."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "dataset": {
                        "type": "string",
                        "description": (
                            "Optional dataset key such as 'weather_2020'. "
                            "Omit to list cities across all datasets."
                        ),
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_datasets",
            "description": "List all loaded datasets with row counts and column names.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },

    # ── Road features ─────────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "query_road_features",
            "description": (
                "Get accidents classified by road feature type "
                "(straight road, curve, bridge, hump, pot holes). "
                "Available years: 2019, 2020."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "year":      {"type": "integer", "enum": [2019, 2020]},
                    "city":      {"type": "string",  "description": "City name to filter (optional)."},
                    "sort_by":   {"type": "string",  "description": "Column to sort by."},
                    "top_n":     {"type": "integer", "description": "Return only the top N rows."},
                    "ascending": {"type": "boolean"},
                },
                "required": ["year"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_road_features_summary",
            "description": "City-wise totals for road feature accidents. Year: 2019 or 2020.",
            "parameters": {
                "type": "object",
                "properties": {"year": {"type": "integer", "enum": [2019, 2020]}},
                "required": ["year"],
            },
        },
    },

    # ── Junctions ─────────────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "query_junctions",
            "description": (
                "Accidents classified by junction type "
                "(T-junction, Y-junction, four-arm, roundabout, staggered, no junction). "
                "Years: 2019, 2020."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "year":      {"type": "integer", "enum": [2019, 2020]},
                    "city":      {"type": "string"},
                    "sort_by":   {"type": "string"},
                    "top_n":     {"type": "integer"},
                    "ascending": {"type": "boolean"},
                },
                "required": ["year"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_junctions_summary",
            "description": "City-wise totals for junction-type accidents. Year: 2019 or 2020.",
            "parameters": {
                "type": "object",
                "properties": {"year": {"type": "integer", "enum": [2019, 2020]}},
                "required": ["year"],
            },
        },
    },

    # ── Traffic control ───────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "query_traffic_control",
            "description": (
                "Accidents by traffic control type "
                "(traffic signal, stop sign, police-controlled, no control). "
                "Years: 2019, 2020."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "year":      {"type": "integer", "enum": [2019, 2020]},
                    "city":      {"type": "string"},
                    "sort_by":   {"type": "string"},
                    "top_n":     {"type": "integer"},
                    "ascending": {"type": "boolean"},
                },
                "required": ["year"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_traffic_control_summary",
            "description": "City-wise totals for traffic control accidents. Year: 2019 or 2020.",
            "parameters": {
                "type": "object",
                "properties": {"year": {"type": "integer", "enum": [2019, 2020]}},
                "required": ["year"],
            },
        },
    },

    # ── Traffic violations ────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "query_traffic_violations",
            "description": (
                "Accidents by traffic violation type "
                "(overspeeding, drunk driving, wrong-side driving, "
                "using mobile phone, jumping red light). "
                "Years: 2019, 2020."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "year":      {"type": "integer", "enum": [2019, 2020]},
                    "city":      {"type": "string"},
                    "sort_by":   {"type": "string"},
                    "top_n":     {"type": "integer"},
                    "ascending": {"type": "boolean"},
                },
                "required": ["year"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_traffic_violations_summary",
            "description": "City-wise totals for traffic violations. Year: 2019 or 2020.",
            "parameters": {
                "type": "object",
                "properties": {"year": {"type": "integer", "enum": [2019, 2020]}},
                "required": ["year"],
            },
        },
    },

    # ── Weather ───────────────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "query_weather",
            "description": (
                "Accidents by weather condition "
                "(fine weather, mist/fog, rain, hail/sleet, snow, "
                "strong winds, dust storm). "
                "Years: 2019, 2020, 2021."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "year":      {"type": "integer", "enum": [2019, 2020, 2021]},
                    "city":      {"type": "string"},
                    "sort_by":   {"type": "string"},
                    "top_n":     {"type": "integer"},
                    "ascending": {"type": "boolean"},
                },
                "required": ["year"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_weather_summary",
            "description": "City-wise totals for weather-condition accidents. Years: 2019, 2020, 2021.",
            "parameters": {
                "type": "object",
                "properties": {"year": {"type": "integer", "enum": [2019, 2020, 2021]}},
                "required": ["year"],
            },
        },
    },

    # ── Vehicles ──────────────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "query_vehicles",
            "description": (
                "Accidents by impacting vehicle/object type "
                "(two-wheeler, auto-rickshaw, car, bus, truck, cyclist, pedestrian). "
                "Year: 2020 only."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "city":      {"type": "string"},
                    "sort_by":   {"type": "string"},
                    "top_n":     {"type": "integer"},
                    "ascending": {"type": "boolean"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_vehicles_summary",
            "description": "City-wise totals for vehicle-type accidents (2020).",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },

    # ── Road defects ──────────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "query_road_defects",
            "description": (
                "State/UT-wise persons killed and injured in accidents "
                "caused by road condition defects. Trend data 2006–2016."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "state":     {"type": "string",  "description": "State or UT name (partial match)."},
                    "year":      {"type": "integer", "description": "Year between 2006 and 2016."},
                    "sort_by":   {"type": "string"},
                    "top_n":     {"type": "integer"},
                    "ascending": {"type": "boolean"},
                },
                "required": [],
            },
        },
    },

    # ── Cross-year comparison ─────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "compare_years",
            "description": (
                "Compare accident data across multiple years for the same category. "
                "Useful for trend questions like "
                "'how did fog accidents change from 2019 to 2021?'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": [
                            "road_features", "junctions",
                            "traffic_control", "traffic_violations",
                            "weather", "vehicles",
                        ],
                    },
                    "years": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "List of years to compare, e.g. [2019, 2020, 2021].",
                    },
                    "city": {"type": "string", "description": "Optional city filter."},
                },
                "required": ["category", "years"],
            },
        },
    },
]


# ── Sarvam tool format ────────────────────────────────────────────────────────
# Sarvam's API expects the same OpenAI-style schema but accessed via
# client.chat.completions(tools=...).
# TOOLS_SARVAM is identical to TOOLS — Sarvam accepts the same format.
TOOLS_SARVAM = TOOLS
