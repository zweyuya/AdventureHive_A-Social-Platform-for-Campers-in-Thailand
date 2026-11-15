from django.urls import path

from . import views

app_name = "ps4"

urlpatterns = [
    path("", views.index, name="index"),
    path("personas/<slug:slug>/", views.persona, name="persona"),
    path("scenarios/<slug:slug>/", views.scenario, name="scenario"),
    path("findings/", views.findings, name="findings"),
    path("requirements/", views.requirements, name="requirements"),
    path("mvp/", views.mvp, name="mvp"),
    path("prototype/", views.prototype, name="prototype"),
]
