# core/urls.py
from django.urls import path
from . import views
from .views import param_graph_page, param_graph_json  

urlpatterns = [

    path("graphs/parameters/", param_graph_page, name="param_graph_page"),     
    path("api/param-graph/",   param_graph_json, name="param_graph_json"),    
]
