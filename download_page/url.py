from django.urls import path
from . import views
urlpatterns = [path('', views.main, name='main_page'), path('api/preview/', views.preview, name='preview'), path('api/start/', views.start, name='start'), path('api/history/', views.history, name='history'), path('api/jobs/<str:identifier>/', views.job_status, name='job'), path('files/<str:identifier>/', views.file_download, name='file'), path('clear/', views.clear_links, name='clear')]
