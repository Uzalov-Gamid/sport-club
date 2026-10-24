from django.urls import path

from . import views

app_name = 'club'

urlpatterns = [
    path('', views.home, name='home'),
    path('clients/', views.clients, name='clients'),
    path('clients/add/', views.client_add, name='client_add'),
    path('clients/<int:pk>/', views.client_detail, name='client'),
    path('clients/<int:pk>/edit/', views.client_edit, name='client_edit'),
    path('clients/<int:pk>/delete/', views.client_delete, name='client_delete'),
    path('clients/<int:pk>/enroll/', views.client_enroll, name='client_enroll'),
    path('clients/<int:pk>/access/', views.client_access_add, name='client_access_add'),
    path('clients/<int:pk>/access/delete/', views.client_access_delete, name='client_access_delete'),
    path('me/', views.me, name='me'),
    path('me/checkin/<int:pk>/', views.me_checkin, name='me_checkin'),
    path('clients/<int:pk>/subscription/', views.subscription_add, name='subscription_add'),
    path('subscriptions/<int:pk>/delete/', views.subscription_delete, name='subscription_delete'),
    path('enrollments/<int:pk>/status/', views.enrollment_status, name='enrollment_status'),
    path('enrollments/<int:pk>/delete/', views.enrollment_delete, name='enrollment_delete'),
    path('enrollments/<int:pk>/visit/', views.visit_mark, name='visit_mark'),
    path('enrollments/<int:pk>/visit/clear/', views.visit_clear, name='visit_clear'),
    path('timetable/', views.timetable, name='timetable'),
    path('groups/add/', views.group_add, name='group_add'),
    path('groups/<int:pk>/', views.group_detail, name='group'),
    path('groups/<int:pk>/edit/', views.group_edit, name='group_edit'),
    path('groups/<int:pk>/delete/', views.group_delete, name='group_delete'),
    path('groups/<int:pk>/enroll/', views.group_enroll, name='group_enroll'),
    path('groups/<int:pk>/attendance/', views.group_attendance, name='group_attendance'),
    path('reports/', views.reports, name='reports'),
    path('catalog/', views.catalog, name='catalog'),
    path('catalog/users/add/', views.user_add, name='user_add'),
    path('catalog/<str:kind>/add/', views.catalog_add, name='catalog_add'),
    path('catalog/<str:kind>/<int:pk>/edit/', views.catalog_edit, name='catalog_edit'),
    path('catalog/<str:kind>/<int:pk>/delete/', views.catalog_delete, name='catalog_delete'),
]
