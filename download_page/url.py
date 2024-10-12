from django.urls import path
from .views import main, clear_links

urlpatterns = [
    path("", main, name="main_page"),
    path("clear/", clear_links, name="clear")
]
