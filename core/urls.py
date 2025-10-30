# urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("graphs/parameters/", views.param_graph_page, name="param_graph_page"),
    path("api/param-graph/", views.param_graph_json, name="param_graph_json"),
    path("api/param-graph/<str:lang_id>/", views.param_graph_json_for_language, name="param_graph_json_lang"),
]
