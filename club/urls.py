from django.urls import path

from . import views

app_name = 'club'

urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),
    path('queries/groups/', views.GroupCountsView.as_view(), name='q_groups'),
    path('queries/gender/', views.SectionGenderView.as_view(), name='q_gender'),
    path('clients/<int:pk>/cost/', views.ClientCostView.as_view(), name='client_cost'),
    path('timetable/', views.TimetableView.as_view(), name='timetable'),
    path('report/schedule/', views.ScheduleReportView.as_view(), name='report'),
    path('users/', views.UserListView.as_view(), name='users'),
]
for _cfg in views.CONFIGS:
    _list, _create, _edit, _delete = views.build_views(_cfg)
    urlpatterns += [
        path(f'{_cfg.key}/', _list, name=_cfg.key),
        path(f'{_cfg.key}/add/', _create, name=f'{_cfg.key}_add'),
        path(f'{_cfg.key}/<int:pk>/edit/', _edit, name=f'{_cfg.key}_edit'),
        path(f'{_cfg.key}/<int:pk>/delete/', _delete, name=f'{_cfg.key}_delete'),
    ]
