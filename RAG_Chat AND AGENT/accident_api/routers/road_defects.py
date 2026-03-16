# road_defects.py
# @'
from fastapi import APIRouter, Query, HTTPException
from typing import Optional
from accident_api.data_loader import loader
from accident_api.routers.helpers import dataset_summary

router = APIRouter()

def _state_col(df):
    for col in df.columns:
        if "state" in col or "ut" in col:
            return col
    return None

@router.get("/")
def road_defects(state: Optional[str]=Query(None), year: Optional[int]=Query(None), sort_by: Optional[str]=Query(None), top_n: Optional[int]=Query(None), ascending: bool=Query(True)):
    df = loader.get("road_defects_2006_2016")
    if df is None:
        raise HTTPException(status_code=404, detail="road_defects_2006_2016 not loaded.")
    if state:
        sc = _state_col(df)
        if sc:
            df = df[df[sc].str.lower().str.contains(state.lower(), na=False)]
    if year:
        yc = next((c for c in df.columns if "year" in c), None)
        if yc:
            df = df[df[yc] == year]
    if sort_by and sort_by in df.columns:
        df = df.sort_values(sort_by, ascending=ascending)
    if top_n:
        df = df.head(top_n)
    return df.to_dict(orient="records")

@router.get("/summary")
def road_defects_summary():
    df = loader.get("road_defects_2006_2016")
    if df is None:
        raise HTTPException(status_code=404, detail="Dataset not loaded.")
    sc = _state_col(df)
    if not sc:
        raise HTTPException(status_code=400, detail="State column not detected.")
    return dataset_summary("road_defects_2006_2016", group_col=sc)
# '@ | Set-Content accident_api\routers\road_defects.py -Encoding UTF8