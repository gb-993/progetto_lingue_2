
from django.urls import path
from . import views

urlpatterns = [
    path("parameters/", views.parameters_graph, name="parameters_graph"),
    path("api/graph.json", views.api_graph, name="api_graph"),
    path("api/lang-values.json", views.api_lang_values, name="api_lang_values"),
]
