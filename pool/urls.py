from django.urls import path
from . import views
from . import admin_views

urlpatterns = [
    path('', views.home, name='home'),
    path('rules/', views.rules, name='rules'),
    
    # Admin views
    path('admin/pick/<int:pick_id>/edit/', admin_views.admin_edit_pick, name='admin_edit_pick'),
    
    path('pool/<int:pool_id>/', views.pool_detail, name='pool_detail'),
    path('entry/<int:entry_id>/', views.entry_detail, name='entry_detail'),
    path('entry/<int:entry_id>/pick/', views.make_pick, name='make_pick'),
    path('pool/<int:pool_id>/quick-pick/', views.quick_pick, name='quick_pick'),
    path('pool/<int:pool_id>/standings/', views.standings, name='standings'),
    path('pool/<int:pool_id>/week/<int:week_number>/', views.week_picks, name='week_picks'),
]
