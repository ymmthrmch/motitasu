from django.urls import path, include
from . import views
from . import admin_views

app_name = 'salary'

urlpatterns = [
    # スキル詳細API
    path('skill-detail/<int:skill_id>/', views.skill_detail_api, name='skill_detail_api'),
    
    # スキル申告API  
    path('apply-skill/', views.apply_skill_api, name='apply_skill_api'),
    
    # 管理者画面
    path('admin/', include([
        # ダッシュボード
        path('dashboard/', admin_views.AdminDashboardView.as_view(), name='admin_dashboard'),
        
        # スキル管理
        path('skills/', admin_views.AdminSkillListView.as_view(), name='admin_skills'),
        path('skills/create/', admin_views.AdminSkillCreateView.as_view(), name='admin_skill_create'),
        path('skills/<int:pk>/', admin_views.AdminSkillDetailView.as_view(), name='admin_skill_detail'),
        path('skills/<int:pk>/edit/', admin_views.AdminSkillEditView.as_view(), name='admin_skill_edit'),
        path('skills/<int:pk>/delete/', admin_views.AdminSkillDeleteAPI.as_view(), name='admin_skill_delete'),
        path('skills/api/holder-revoke/', admin_views.AdminRevokeSkillAPI.as_view(), name='admin_revoke_skill'),
        
        # 給与グレード管理
        path('grades/', admin_views.AdminGradeListView.as_view(), name='admin_grades'),
        path('grades/create/', admin_views.AdminGradeCreateView.as_view(), name='admin_grade_create'),
        path('grades/<int:pk>/', admin_views.AdminGradeDetailView.as_view(), name='admin_grade_detail'),
        path('grades/<int:pk>/edit/', admin_views.AdminGradeEditView.as_view(), name='admin_grade_edit'),
        path('grades/<int:pk>/delete/', admin_views.AdminGradeDeleteAPI.as_view(), name='admin_grade_delete'),
        
        # ユーザー管理
        path('user-management/', admin_views.AdminUserManagementView.as_view(), name='admin_user_management'),
        path('user-management/<int:user_id>/', admin_views.AdminUserDetailView.as_view(), name='admin_user_detail'),
        path('user-management/api/grant-skill/', admin_views.AdminGrantSkillAPI.as_view(), name='admin_grant_skill'),
        path('user-management/api/revoke-skill/', admin_views.AdminRevokeUserSkillAPI.as_view(), name='admin_revoke_user_skill'),
        path('user-management/api/change-grade/', admin_views.AdminChangeGradeAPI.as_view(), name='admin_change_grade'),
        
        # 申告承認
        path('applications/', admin_views.AdminApplicationListView.as_view(), name='admin_applications'),
        path('applications/pending/', admin_views.AdminApplicationListView.as_view(), name='admin_applications_pending'),
        path('applications/<int:pk>/review/', admin_views.AdminApplicationReviewView.as_view(), name='admin_application_review'),
        path('applications/api/bulk-approve/', admin_views.AdminBulkApproveAPI.as_view(), name='admin_bulk_approve'),
        path('applications/api/bulk-reject/', admin_views.AdminBulkRejectAPI.as_view(), name='admin_bulk_reject'),
        path('applications/api/<int:pk>/approve/', admin_views.AdminApproveApplicationAPI.as_view(), name='admin_approve_application'),
        path('applications/api/<int:pk>/reject/', admin_views.AdminRejectApplicationAPI.as_view(), name='admin_reject_application'),
    ])),
]