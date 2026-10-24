from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from club.pwa import manifest, service_worker

urlpatterns = [
    path('manifest.webmanifest', manifest, name='manifest'),
    path('sw.js', service_worker, name='sw'),
    path('admin/', admin.site.urls),
    path('login/', auth_views.LoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('', include('club.urls')),
]
