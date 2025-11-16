from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('api/processes/', views.get_processes, name='get_processes'),
]