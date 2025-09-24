from django.urls import path, include
from . import views

app_name = 'salary'

urlpatterns = [
    # スキル詳細API
    path('skill-detail/<int:skill_id>/', views.skill_detail_api, name='skill_detail_api'),
    
    # スキル申告API  
    path('apply-skill/', views.apply_skill_api, name='apply_skill_api'),
    
    # 管理者画面
    path('admin/', include([
        # ダッシュボード
        path('dashboard/', views.AdminDashboardView.as_view(), name='admin_dashboard'),
        
        # スキル管理
        path('skills/', views.AdminSkillListView.as_view(), name='admin_skills'),
        path('skills/create/', views.AdminSkillCreateView.as_view(), name='admin_skill_create'),
        path('skills/<int:pk>/edit/', views.AdminSkillEditView.as_view(), name='admin_skill_edit'),
        path('skills/<int:pk>/holders/', views.AdminSkillHoldersView.as_view(), name='admin_skill_holders'),
        path('skills/<int:pk>/delete/', views.AdminSkillDeleteAPI.as_view(), name='admin_skill_delete'),
        path('skills/api/holder-revoke/', views.AdminRevokeSkillAPI.as_view(), name='admin_revoke_skill'),
        
        # 給与グレード管理
        path('grades/', views.AdminGradeListView.as_view(), name='admin_grades'),
        path('grades/create/', views.AdminGradeCreateView.as_view(), name='admin_grade_create'),
        path('grades/<int:pk>/edit/', views.AdminGradeEditView.as_view(), name='admin_grade_edit'),
        path('grades/<int:pk>/members/', views.AdminGradeMembersView.as_view(), name='admin_grade_members'),
        path('grades/<int:pk>/delete/', views.AdminGradeDeleteAPI.as_view(), name='admin_grade_delete'),
        
        # ユーザー管理
        path('user-management/', views.AdminUserManagementView.as_view(), name='admin_user_management'),
        path('user-management/<int:user_id>/', views.AdminUserDetailView.as_view(), name='admin_user_detail'),
        path('user-management/api/grant-skill/', views.AdminGrantSkillAPI.as_view(), name='admin_grant_skill'),
        path('user-management/api/revoke-skill/', views.AdminRevokeUserSkillAPI.as_view(), name='admin_revoke_user_skill'),
        path('user-management/api/change-grade/', views.AdminChangeGradeAPI.as_view(), name='admin_change_grade'),
        
        # 申告承認
        path('applications/', views.AdminApplicationListView.as_view(), name='admin_applications'),
        path('applications/pending/', views.AdminApplicationListView.as_view(), name='admin_applications_pending'),
        path('applications/<int:pk>/review/', views.AdminApplicationReviewView.as_view(), name='admin_application_review'),
        path('applications/api/bulk-approve/', views.AdminBulkApproveAPI.as_view(), name='admin_bulk_approve'),
        path('applications/api/bulk-reject/', views.AdminBulkRejectAPI.as_view(), name='admin_bulk_reject'),
        path('applications/api/<int:pk>/approve/', views.AdminApproveApplicationAPI.as_view(), name='admin_approve_application'),
        path('applications/api/<int:pk>/reject/', views.AdminRejectApplicationAPI.as_view(), name='admin_reject_application'),
    ])),
]