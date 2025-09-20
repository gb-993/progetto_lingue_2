from django.urls import path
from . import views
urlpatterns = [
    path("", views.tablea_index, name="tablea_index"),
    path("export.xlsx", views.tablea_export_xlsx, name="tablea_export_xlsx"),
    path("export.csv",  views.tablea_export_csv,  name="tablea_export_csv"),
]
