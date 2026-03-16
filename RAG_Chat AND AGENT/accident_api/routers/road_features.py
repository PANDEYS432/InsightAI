# road_features.py
from fastapi import APIRouter, Query
from typing import Optional
from accident_api.routers.helpers import dataset_query, dataset_summary

router = APIRouter()

@router.get("/2019")
def road_features_2019(city: Optional[str]=Query(None), sort_by: Optional[str]=Query(None), top_n: Optional[int]=Query(None), ascending: bool=Query(True)):
    return dataset_query("road_features_2019", city=city, sort_by=sort_by, top_n=top_n, ascending=ascending)

@router.get("/2019/summary")
def road_features_2019_summary():
    return dataset_summary("road_features_2019")

@router.get("/2020")
def road_features_2020(city: Optional[str]=Query(None), sort_by: Optional[str]=Query(None), top_n: Optional[int]=Query(None), ascending: bool=Query(True)):
    return dataset_query("road_features_2020", city=city, sort_by=sort_by, top_n=top_n, ascending=ascending)

@router.get("/2020/summary")
def road_features_2020_summary():
    return dataset_summary("road_features_2020")
