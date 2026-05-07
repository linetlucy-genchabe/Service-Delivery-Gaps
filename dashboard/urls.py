from django.urls import path
from . import views

urlpatterns = [
    path('healthz/', views.healthz, name='healthz'),
    path('login/',  views.login_view,  name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('', views.dashboard_view, name='dashboard'),
    path('upload/',                    views.upload_view,        name='upload'),
    path('upload/delete/<int:pk>/',    views.delete_batch_view,  name='delete_batch'),
    path('api/unsupervised/',          views.api_unsupervised,   name='api_unsupervised'),
    path('api/low-performers/',        views.api_low_performers,  name='api_low_performers'),
    path('api/same-day-flags/',        views.api_same_day_flags,  name='api_same_day_flags'),
    path('api/anc-gap/',               views.api_anc_gap,         name='api_anc_gap'),
    path('download/unsupervised/',     views.download_unsupervised,   name='download_unsupervised'),
    path('download/low-performers/',   views.download_low_performers,  name='download_low_performers'),
    path('download/same-day-flags/',   views.download_same_day_flags,  name='download_same_day_flags'),
    path('download/anc-gap/',          views.download_anc_gap,         name='download_anc_gap'),
]