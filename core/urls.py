from django.urls import path
from .views import (
    param_graph_page,
    param_graph_json,
    param_graph_json_for_language,
)

urlpatterns = [
    path("graphs/params/", param_graph_page, name="param_graph_page"),                                   # unchanged
    path("graphs/parameters/", param_graph_page, name="param_graph_page_alias"),                         # CHG: alias
    path("api/param-graph/", param_graph_json, name="param_graph_json"),
    path("api/param-graph/lang/<str:lang_id>/", param_graph_json_for_language, name="param_graph_json_for_language"),
]
