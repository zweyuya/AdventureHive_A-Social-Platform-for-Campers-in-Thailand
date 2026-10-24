from django.urls import path

from . import views

auth_urlpatterns = [
    path("csrf/", views.CsrfView.as_view(), name="auth-csrf"),
    path("register/", views.RegisterView.as_view(), name="auth-register"),
    path("login/", views.LoginView.as_view(), name="auth-login"),
    path("token/refresh/", views.RefreshView.as_view(), name="auth-refresh"),
    path("logout/", views.LogoutView.as_view(), name="auth-logout"),
    path("account/", views.AccountDeleteView.as_view(), name="auth-account"),
]

users_urlpatterns = [
    path("me/", views.MeView.as_view(), name="users-me"),
    path("<int:pk>/", views.UserProfileView.as_view(), name="users-detail"),
    path("<int:pk>/emergency-contact/", views.EmergencyContactView.as_view(),
         name="users-emergency-contact"),
]
