# helpers.py
from fastapi import HTTPException
from typing import Optional, List, Dict, Any
from accident_api.data_loader import loader

def dataset_query(dataset_key, city=None, sort_by=None, ascending=True, top_n=None):
    try:
        return loader.query(key=dataset_key, city=city, sort_by=sort_by, ascending=ascending, top_n=top_n)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Query error: {exc}")

def dataset_summary(dataset_key, group_col="city", value_col=None):
    try:
        return loader.summarize(key=dataset_key, group_col=group_col, value_col=value_col)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Summary error: {exc}")
