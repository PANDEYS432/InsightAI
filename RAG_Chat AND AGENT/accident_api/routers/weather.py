# weather.py
# @'
from fastapi import APIRouter, Query
from typing import Optional
from accident_api.routers.helpers import dataset_query, dataset_summary

router = APIRouter()

@router.get("/2019")
def weather_2019(city: Optional[str]=Query(None), sort_by: Optional[str]=Query(None), top_n: Optional[int]=Query(None), ascending: bool=Query(True)):
    return dataset_query("weather_2019", city=city, sort_by=sort_by, top_n=top_n, ascending=ascending)

@router.get("/2019/summary")
def weather_2019_summary():
    return dataset_summary("weather_2019")

@router.get("/2020")
def weather_2020(city: Optional[str]=Query(None), sort_by: Optional[str]=Query(None), top_n: Optional[int]=Query(None), ascending: bool=Query(True)):
    return dataset_query("weather_2020", city=city, sort_by=sort_by, top_n=top_n, ascending=ascending)

@router.get("/2020/summary")
def weather_2020_summary():
    return dataset_summary("weather_2020")

@router.get("/2021")
def weather_2021(city: Optional[str]=Query(None), sort_by: Optional[str]=Query(None), top_n: Optional[int]=Query(None), ascending: bool=Query(True)):
    return dataset_query("weather_2021", city=city, sort_by=sort_by, top_n=top_n, ascending=ascending)

@router.get("/2021/summary")
def weather_2021_summary():
    return dataset_summary("weather_2021")
# '@ | Set-Content accident_api\routers\weather.py -Encoding UTF8