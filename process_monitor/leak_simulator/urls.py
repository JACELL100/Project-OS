from django.urls import path
from . import views

app_name = 'leak_simulator'

urlpatterns = [
    path('sim/', views.index, name='index'),
    path('api/start/', views.start_simulator, name='start_simulator'),
    path('api/stop/', views.stop_simulator, name='stop_simulator'),
    path('api/status/', views.get_status, name='get_status'),
    path('api/leak-processes/', views.get_leak_processes, name='get_leak_processes'),
]