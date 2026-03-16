from fastapi import APIRouter, Query
from typing import Optional
from accident_api.routers.helpers import dataset_query, dataset_summary

router = APIRouter()

@router.get("/2020")
def vehicles_2020(city: Optional[str]=Query(None), sort_by: Optional[str]=Query(None), top_n: Optional[int]=Query(None), ascending: bool=Query(True)):
    return dataset_query("vehicles_2020", city=city, sort_by=sort_by, top_n=top_n, ascending=ascending)

@router.get("/2020/summary")
def vehicles_2020_summary():
    return dataset_summary("vehicles_2020")