from django.urls import path
from . import views 

urlpatterns = [
    path('instructions/', views.instruction, name='instruction'),
    path('api/update-content/', views.update_site_content, name='update_site_content'),
]