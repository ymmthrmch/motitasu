from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import TemplateView, ListView, CreateView, UpdateView, DetailView, View
from django.http import JsonResponse
from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.db import models
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
import json

from .decorators import AdminRequiredMixin, admin_required_api, log_admin_action
from .models import Skill, SalaryGrade, UserSkill, SkillApplication, UserSalaryGrade, AdminActionLog

User = get_user_model()


# ======= ダッシュボード =======
class AdminDashboardView(AdminRequiredMixin, TemplateView):
    template_name = 'salary/admin/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 統計データ
        context.update({
            'total_users': User.objects.count(),
            'total_skills': Skill.objects.count(),
            'total_grades': SalaryGrade.objects.count(),
            'pending_applications': SkillApplication.objects.filter(status='pending').count(),
            
            # スキル別習得者マップ
            'skills_map': Skill.objects.prefetch_related(
                'userskill_set__user'
            ).annotate(
                holders_count=Count('userskill')
            )[:10],
            
            # グレード別所属者マップ
            'grades_map': SalaryGrade.objects.prefetch_related(
                'usersalarygrade_set__user'
            ).annotate(
                members_count=Count('usersalarygrade__id')
            ).order_by('level'),
            
            # 最近の活動ログ
            'recent_actions': AdminActionLog.objects.select_related(
                'admin_user', 'target_user'
            ).order_by('-timestamp')[:10],
        })
        return context


# ======= スキル管理 =======
class AdminSkillListView(AdminRequiredMixin, ListView):
    model = Skill
    template_name = 'salary/admin/skills/list.html'
    context_object_name = 'skills'
    
    def get_queryset(self):
        return Skill.objects.annotate(
            holders_count=Count('userskill')
        ).order_by('category', 'name')


class AdminSkillCreateView(AdminRequiredMixin, CreateView):
    model = Skill
    template_name = 'salary/admin/skills/create.html'
    fields = ['name', 'description', 'category']
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['name'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'スキル名を入力してください'
        })
        form.fields['description'].widget.attrs.update({
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'このスキルの内容や習得要件について詳しく記載してください'
        })
        form.fields['category'].widget.attrs.update({
            'class': 'form-select'
        })
        return form
    
    def get_success_url(self):
        return '/salary/admin/skills/'
    
    @log_admin_action('skill_create')
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'スキル「{self.object.name}」を作成しました。')
        return response


class AdminSkillDetailView(DetailView):
    model = Skill
    template_name = 'salary/admin/skills/detail.html'
    context_object_name = 'skill'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 習得者数と習得者一覧
        holders = self.object.userskill_set.select_related(
            'user', 'approved_by'
        ).order_by('-acquired_date')
        context['holders'] = holders
        context['holders_count'] = holders.count()
        
        # このスキルを要求する給与グレード
        required_grades = self.object.salarygrade_set.all().order_by('level')
        context['required_grades'] = required_grades
        
        # スキル統計
        total_users = User.objects.count()
        context['acquisition_rate'] = (context['holders_count'] / total_users * 100) if total_users > 0 else 0
        
        return context


class AdminSkillEditView(AdminRequiredMixin, UpdateView):
    model = Skill
    template_name = 'salary/admin/skills/edit.html'
    fields = ['name', 'description', 'category']
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['name'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'スキル名を入力してください'
        })
        form.fields['description'].widget.attrs.update({
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'このスキルの内容や習得要件について詳しく記載してください'
        })
        form.fields['category'].widget.attrs.update({
            'class': 'form-select'
        })
        return form
    
    def get_success_url(self):
        return '/salary/admin/skills/'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        holders_count = self.object.userskill_set.count()
        context['holders_count'] = holders_count
        # skillオブジェクトにholders_count属性を追加（テンプレートで使用）
        self.object.holders_count = holders_count
        return context
    
    @log_admin_action('skill_edit')
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'スキル「{self.object.name}」を更新しました。')
        return response


class AdminSkillHoldersView(AdminRequiredMixin, DetailView):
    model = Skill
    template_name = 'salary/admin/skills/holders.html'
    context_object_name = 'skill'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['holders'] = self.object.userskill_set.select_related(
            'user', 'approved_by'
        ).order_by('-acquired_date')
        return context


class AdminSkillDeleteAPI(AdminRequiredMixin, View):
    @admin_required_api
    def post(self, request, pk):
        try:
            skill = get_object_or_404(Skill, pk=pk)
            skill_name = skill.name
            holders_count = skill.userskill_set.count()
            
            with transaction.atomic():
                # 習得者がいる場合はUserSkillレコードも削除
                if holders_count > 0:
                    UserSkill.objects.filter(skill=skill).delete()
                
                # スキル本体を削除
                skill.delete()
                
                # 管理者操作ログを記録
                AdminActionLog.objects.create(
                    admin_user=request.user,
                    action='skill_delete',
                    description=f'スキル「{skill_name}」を削除しました（習得者: {holders_count}人）'
                )
            
            return JsonResponse({
                'status': 'success',
                'message': f'スキル「{skill_name}」を削除しました。'
            })
            
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': f'削除処理中にエラーが発生しました: {str(e)}'
            })


class AdminRevokeSkillAPI(AdminRequiredMixin, View):
    @admin_required_api
    def post(self, request):
        try:
            data = json.loads(request.body)
            user_id = data.get('user_id')
            skill_id = data.get('skill_id')
            
            if not user_id or not skill_id:
                return JsonResponse({
                    'status': 'error',
                    'message': '必要なパラメータが不足しています。'
                })
            
            user = get_object_or_404(User, pk=user_id)
            skill = get_object_or_404(Skill, pk=skill_id)
            
            with transaction.atomic():
                # UserSkillレコードを削除（これによりダッシュボードで「未習得」表示になる）
                user_skill = UserSkill.objects.filter(user=user, skill=skill).first()
                if not user_skill:
                    return JsonResponse({
                        'status': 'error',
                        'message': 'このユーザーは指定されたスキルを習得していません。'
                    })
                
                user_skill.delete()
                
                # 管理者操作ログを記録
                AdminActionLog.objects.create(
                    admin_user=request.user,
                    action='skill_revoke',
                    target_user=user,
                    description=f'{user.name}さんのスキル「{skill.name}」習得を取り消しました'
                )
            
            return JsonResponse({
                'status': 'success',
                'message': f'{user.name}さんの「{skill.name}」スキル習得を取り消しました。'
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'status': 'error',
                'message': '無効なリクエストデータです。'
            })
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': f'処理中にエラーが発生しました: {str(e)}'
            })


# ======= 給与グレード管理 =======
class AdminGradeListView(AdminRequiredMixin, ListView):
    model = SalaryGrade
    template_name = 'salary/admin/grades/list.html'
    context_object_name = 'grades'
    
    def get_queryset(self):
        # 現在のグレード所属者数をアノテーション（UserSalaryGrade経由）
        return SalaryGrade.objects.annotate(
            members_count=Count('usersalarygrade', distinct=True)
        ).order_by('level')


class AdminGradeCreateView(AdminRequiredMixin, CreateView):
    model = SalaryGrade
    template_name = 'salary/admin/grades/create.html'
    fields = ['name', 'description', 'hourly_wage', 'level', 'required_skills', 'next_possible_grades']
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['name'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'グレード名を入力してください'
        })
        form.fields['description'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'グレードの説明を入力してください（任意）',
            'rows': '3'
        })
        form.fields['hourly_wage'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': '1000',
            'type': 'number',
            'min': '0',
            'step': '1'
        })
        form.fields['level'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': '1',
            'type': 'number',
            'min': '1'
        })
        # ManyToManyフィールドは非表示にして、カスタムUIで処理
        form.fields['required_skills'].widget.attrs.update({
            'style': 'display: none;',
            'multiple': True
        })
        form.fields['next_possible_grades'].widget.attrs.update({
            'style': 'display: none;',
            'multiple': True
        })
        return form
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['all_skills'] = Skill.objects.all().order_by('name')
        context['all_grades'] = SalaryGrade.objects.all().order_by('level')
        return context
    
    def get_success_url(self):
        return '/salary/admin/grades/'
    
    @log_admin_action('grade_create')
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'グレード「{self.object.name}」を作成しました。')
        return response


class AdminGradeDetailView(DetailView):
    model = SalaryGrade
    template_name = 'salary/admin/grades/detail.html'
    context_object_name = 'grade'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 現在の所属者数（UserSalaryGradeの最新レコードから）
        current_members = UserSalaryGrade.objects.filter(
            salary_grade=self.object
        ).select_related('user', 'changed_by').order_by('-effective_date')
        
        # 重複ユーザーを除去（最新レコードのみ）
        seen_users = set()
        unique_members = []
        for member in current_members:
            if member.user_id not in seen_users:
                unique_members.append(member)
                seen_users.add(member.user_id)
        
        context['current_members'] = unique_members
        context['members_count'] = len(unique_members)
        
        # 必要スキル
        context['required_skills'] = self.object.required_skills.all().order_by('name')
        
        # 昇進先グレード
        context['next_grades'] = self.object.next_possible_grades.all().order_by('level')
        
        # このグレードから昇進可能なグレード（逆方向）
        context['promotion_from_grades'] = SalaryGrade.objects.filter(
            next_possible_grades=self.object
        ).order_by('level')
        
        # 統計情報
        total_users = User.objects.count()
        context['occupation_rate'] = (context['members_count'] / total_users * 100) if total_users > 0 else 0
        
        # 昇進条件達成者（このグレードへの昇進条件を満たし、現在のグレードから昇進可能なユーザー）
        if context['required_skills']:
            required_skill_ids = set(self.object.required_skills.values_list('id', flat=True))
            eligible_users_list = []
            for user in User.objects.prefetch_related('userskill_set'):
                # 必要スキルをすべて持っているかチェック
                user_skill_ids = set(user.userskill_set.values_list('skill_id', flat=True))
                if required_skill_ids.issubset(user_skill_ids):
                    # ユーザーの現在の給与グレードを取得
                    current_grade = user.current_salary_grade
                    if current_grade and current_grade.next_possible_grades.filter(id=self.object.id).exists():
                        # 現在のグレードの昇進先にこのグレードが含まれている場合のみ追加
                        eligible_users_list.append(user)
            context['eligible_users'] = eligible_users_list
            context['eligible_users_count'] = len(eligible_users_list)
        else:
            # 必要スキルがない場合でも昇進経路をチェック
            eligible_users_list = []
            for user in User.objects.all():
                current_grade = user.current_salary_grade
                if current_grade and current_grade.next_possible_grades.filter(id=self.object.id).exists():
                    eligible_users_list.append(user)
            context['eligible_users'] = eligible_users_list
            context['eligible_users_count'] = len(eligible_users_list)
            
        return context


class AdminGradeEditView(AdminRequiredMixin, UpdateView):
    model = SalaryGrade
    template_name = 'salary/admin/grades/edit.html'
    fields = ['name', 'description', 'hourly_wage', 'level', 'required_skills', 'next_possible_grades']
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['name'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'グレード名を入力してください'
        })
        form.fields['description'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'グレードの説明を入力してください（任意）',
            'rows': '3'
        })
        form.fields['hourly_wage'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': '1000',
            'type': 'number',
            'min': '0',
            'step': '1'
        })
        form.fields['level'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': '1',
            'type': 'number',
            'min': '1'
        })
        # ManyToManyフィールドは非表示にして、カスタムUIで処理
        form.fields['required_skills'].widget.attrs.update({
            'style': 'display: none;',
            'multiple': True
        })
        form.fields['next_possible_grades'].widget.attrs.update({
            'style': 'display: none;',
            'multiple': True
        })
        return form
    
    def get_success_url(self):
        return '/salary/admin/grades/'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # 現在のグレード所属者数を取得 - UserSalaryGradeから最新のレコードで判定
        from salary.models import UserSalaryGrade
        latest_grade_users = UserSalaryGrade.objects.filter(
            salary_grade=self.object
        ).values('user').annotate(
            latest_date=models.Max('effective_date')
        )
        members_count = latest_grade_users.count()
        context['members_count'] = members_count
        # gradeオブジェクトにmembers_countを追加（テンプレートで使用）
        context['grade'] = self.object
        context['grade'].members_count = members_count
        
        # スキルとグレードの選択肢を追加
        context['all_skills'] = Skill.objects.all().order_by('name')
        context['all_grades'] = SalaryGrade.objects.exclude(id=self.object.id).order_by('level')
        return context
    
    @log_admin_action('grade_edit')
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'グレード「{self.object.name}」を更新しました。')
        return response


class AdminGradeMembersView(AdminRequiredMixin, DetailView):
    model = SalaryGrade
    template_name = 'salary/admin/grades/members.html'
    context_object_name = 'grade'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['members'] = self.object.usersalarygrade_set.select_related(
            'user', 'changed_by'
        ).order_by('-effective_date')
        return context


class AdminGradeDeleteAPI(AdminRequiredMixin, View):
    @admin_required_api
    def post(self, request, pk):
        try:
            grade = get_object_or_404(SalaryGrade, pk=pk)
            grade_name = grade.name
            
            # 所属者数をチェック
            # 現在のグレード所属者数をチェック（UserSalaryGradeの最新レコードで判定）
            from salary.models import UserSalaryGrade
            latest_grade_users = UserSalaryGrade.objects.filter(
                salary_grade=grade
            ).values('user').annotate(
                latest_date=models.Max('effective_date')
            )
            members_count = latest_grade_users.count()
            
            if members_count > 0:
                return JsonResponse({
                    'status': 'error',
                    'message': f'このグレードには現在{members_count}人が所属しているため削除できません。先に所属者のグレードを変更してください。'
                })
            
            with transaction.atomic():
                # 過去の履歴はそのまま残す（end_dateが設定されているもの）
                # グレード本体を削除
                grade.delete()
                
                # 管理者操作ログを記録
                AdminActionLog.objects.create(
                    admin_user=request.user,
                    action='grade_delete',
                    description=f'給与グレード「{grade_name}」を削除しました'
                )
            
            return JsonResponse({
                'status': 'success',
                'message': f'給与グレード「{grade_name}」を削除しました。'
            })
            
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': f'削除処理中にエラーが発生しました: {str(e)}'
            })


# ======= ユーザー管理 =======
class AdminUserManagementView(AdminRequiredMixin, ListView):
    model = User
    template_name = 'salary/admin/user_management/list.html'
    context_object_name = 'users'
    paginate_by = 50
    
    def get_queryset(self):
        queryset = User.objects.prefetch_related(
            'userskill_set__skill', 'salary_history__salary_grade'
        ).order_by('name')
        
        # 検索フィルタ
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | 
                Q(email__icontains=search)
            )
        
        # グレードフィルタ - UserSalaryGradeの最新レコードで判定
        grade_id = self.request.GET.get('grade')
        if grade_id == 'none':
            # グレード未設定のユーザーを取得
            users_with_grades = UserSalaryGrade.objects.values('user').distinct()
            queryset = queryset.exclude(id__in=users_with_grades)
        elif grade_id:
            # 指定されたグレードに所属するユーザーを取得
            latest_grade_users = UserSalaryGrade.objects.filter(
                salary_grade_id=grade_id
            ).values('user')
            queryset = queryset.filter(id__in=latest_grade_users)
        
        # スキルフィルタ
        skill_id = self.request.GET.get('skill')
        if skill_id:
            queryset = queryset.filter(userskill__skill_id=skill_id)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['salary_grades'] = SalaryGrade.objects.order_by('level')
        context['skills'] = Skill.objects.order_by('name')
        
        # 各ユーザーに昇進条件情報を追加
        users = context['users']
        for user in users:
            user.promotion_conditions = self._get_promotion_conditions(user)
        
        return context
    
    def _get_current_salary_grade(self, user):
        """ユーザーの現在の給与グレードを取得"""
        latest_grade = UserSalaryGrade.objects.filter(
            user=user
        ).select_related('salary_grade').order_by('-effective_date').first()
        return latest_grade.salary_grade if latest_grade else None
    
    def _get_promotion_conditions(self, user):
        """ユーザーの昇進条件をチェック"""
        current_grade = user.current_salary_grade
        if not current_grade:
            return []
        
        # 現在のグレードから昇進可能な次のグレードを取得
        next_grades = current_grade.next_possible_grades.prefetch_related('required_skills').all()
        
        # ユーザーが習得済みのスキルを取得
        user_skills = set(user.userskill_set.values_list('skill_id', flat=True))
        
        promotion_conditions = []
        for next_grade in next_grades:
            # 必要スキルを取得
            required_skills = set(next_grade.required_skills.values_list('id', flat=True))
            
            # 習得済みスキルと必要スキルを比較
            missing_skills = required_skills - user_skills
            can_promote = len(missing_skills) == 0
            
            promotion_conditions.append({
                'grade': next_grade,
                'can_promote': can_promote,
                'required_skills': required_skills,
                'missing_skills': missing_skills,
                'missing_skills_count': len(missing_skills)
            })
        
        return promotion_conditions


class AdminUserDetailView(AdminRequiredMixin, DetailView):
    model = User
    template_name = 'salary/admin/user_management/detail.html'
    context_object_name = 'target_user'
    pk_url_kwarg = 'user_id'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.get_object()

        # ユーザーの習得スキル
        context['user_skills'] = user.userskill_set.select_related(
            'skill', 'approved_by'
        ).order_by('-acquired_date')

        # 利用可能なスキル（未習得のもの）
        acquired_skill_ids = context['user_skills'].values_list('skill_id', flat=True)
        context['available_skills'] = Skill.objects.exclude(
            id__in=acquired_skill_ids
        ).order_by('name')

        # 利用可能なグレード
        context['available_grades'] = SalaryGrade.objects.order_by('level')

        # 現在のグレード所属情報（最新のUserSalaryGradeレコード）
        current_grade_member = UserSalaryGrade.objects.filter(
            user=user
        ).select_related('salary_grade').order_by('-effective_date').first()

        context['current_grade_member'] = current_grade_member
        context['current_salary_grade'] = current_grade_member.salary_grade if current_grade_member else None

        # グレード変更履歴
        context['grade_history'] = UserSalaryGrade.objects.filter(
            user=user
        ).select_related('salary_grade', 'changed_by').order_by('-effective_date')[:10]

        # 昇進条件達成グレード（現在のグレードのnext_possible_gradesのみ）
        user_skill_ids = set(context['user_skills'].values_list('skill_id', flat=True))
        eligible_grades = []
        ineligible_grade_entries = []  # ← 追加: 未達成グレードと不足スキル

        if context['current_salary_grade']:
            # 必要スキルをまとめてprefetch
            next_possible_grades = context['current_salary_grade']\
                .next_possible_grades.prefetch_related('required_skills')

            for grade in next_possible_grades:
                required_skill_ids = set(grade.required_skills.values_list('id', flat=True))

                total_required_skills = len(required_skill_ids)
                acquired_skills_for_grade = len(required_skill_ids & user_skill_ids)
                
                if not required_skill_ids or required_skill_ids.issubset(user_skill_ids):
                    # 必要スキルなし、またはすべて満たしている → 達成
                    eligible_grades.append({
                        'grade': grade,
                        'acquired_count': acquired_skills_for_grade,
                        'required_count': total_required_skills,
                    })
                else:
                    # 未達成 → 不足スキルを抽出してcontextに渡す
                    missing_ids = required_skill_ids - user_skill_ids
                    # 必要に応じてSkillオブジェクトを渡したいのでQuerySetで取得
                    missing_skills_qs = grade.required_skills.filter(id__in=missing_ids).order_by('name')
                    ineligible_grade_entries.append({
                        'grade': grade,
                        'missing_skills': list(missing_skills_qs),
                        'acquired_count': acquired_skills_for_grade,
                        'required_count': total_required_skills,
                    })

        # レベル順ソート
        eligible_grades.sort(key=lambda x: x['grade'].level)
        ineligible_grade_entries.sort(key=lambda e: e['grade'].level)

        context['eligible_grades'] = eligible_grades
        context['ineligible_grades'] = ineligible_grade_entries

        # 統計情報
        # 習得スキル数
        context['acquired_skills_count'] = context['user_skills'].count()
        
        # 勤続年数（入社日から現在まで）
        if hasattr(user, 'hire_date') and user.hire_date:
            from datetime import date
            today = date.today()
            service_days = (today - user.hire_date).days
            context['service_years'] = round(service_days / 365.25, 1)  # 年数（小数点1桁）
            context['service_days'] = service_days
        else:
            context['service_years'] = None
            context['service_days'] = None
        
        # 総出勤日数（timeclockアプリのAttendanceRecordから取得）
        try:
            from timeclock.models import AttendanceRecord
            # 出勤記録の総数を取得
            total_attendance = AttendanceRecord.objects.filter(
                user=user,
                time_out__isnull=False  # 退勤記録がある = 完了した出勤
            ).count()
            context['total_attendance_days'] = total_attendance
        except ImportError:
            # timeclockアプリが存在しない場合
            context['total_attendance_days'] = None

        return context



class AdminGrantSkillAPI(AdminRequiredMixin, View):
    @admin_required_api
    def post(self, request):
        try:
            data = json.loads(request.body)
            user_id = data.get('user_id')
            skill_id = data.get('skill_id')
            
            if not user_id or not skill_id:
                return JsonResponse({
                    'status': 'error',
                    'message': '必要なパラメータが不足しています。'
                })
            
            user = get_object_or_404(User, pk=user_id)
            skill = get_object_or_404(Skill, pk=skill_id)
            
            # 重複付与チェック
            if UserSkill.objects.filter(user=user, skill=skill).exists():
                return JsonResponse({
                    'status': 'error',
                    'message': f'{user.name}さんは既に「{skill.name}」スキルを習得しています。'
                })
            
            with transaction.atomic():
                # UserSkillレコードを作成
                UserSkill.objects.create(
                    user=user,
                    skill=skill,
                    acquired_date=timezone.now(),
                    approved_by=request.user
                )
                
                # 管理者操作ログを記録
                AdminActionLog.objects.create(
                    admin_user=request.user,
                    action='skill_grant',
                    target_user=user,
                    description=f'{user.name}さんにスキル「{skill.name}」を手動付与しました'
                )
            
            return JsonResponse({
                'status': 'success',
                'message': f'{user.name}さんに「{skill.name}」スキルを付与しました。'
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'status': 'error',
                'message': '無効なリクエストデータです。'
            })
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': f'処理中にエラーが発生しました: {str(e)}'
            })


class AdminRevokeUserSkillAPI(AdminRequiredMixin, View):
    @admin_required_api
    def post(self, request):
        try:
            data = json.loads(request.body)
            user_skill_id = data.get('user_skill_id')
            
            if not user_skill_id:
                return JsonResponse({
                    'status': 'error',
                    'message': '必要なパラメータが不足しています。'
                })
            
            user_skill = get_object_or_404(UserSkill, pk=user_skill_id)
            user_name = user_skill.user.name
            skill_name = user_skill.skill.name
            
            with transaction.atomic():
                # UserSkillレコードを削除してダッシュボードで「未習得」表示に
                user_skill.delete()
                
                # 管理者操作ログを記録
                AdminActionLog.objects.create(
                    admin_user=request.user,
                    action='skill_revoke',
                    target_user=user_skill.user,
                    description=f'{user_name}さんのスキル「{skill_name}」習得を取り消しました'
                )
            
            return JsonResponse({
                'status': 'success',
                'message': f'{user_name}さんの「{skill_name}」スキル習得を取り消しました。'
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'status': 'error',
                'message': '無効なリクエストデータです。'
            })
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': f'処理中にエラーが発生しました: {str(e)}'
            })


class AdminChangeGradeAPI(AdminRequiredMixin, View):
    @admin_required_api
    def post(self, request):
        try:
            data = json.loads(request.body)
            user_id = data.get('user_id')
            grade_id = data.get('grade_id')
            
            if not user_id or not grade_id:
                return JsonResponse({
                    'status': 'error',
                    'message': '必要なパラメータが不足しています。'
                })
            
            user = get_object_or_404(User, pk=user_id)
            new_grade = get_object_or_404(SalaryGrade, pk=grade_id)
            
            # 現在のグレードと同じかチェック
            current_grade_member = UserSalaryGrade.objects.filter(
                user=user
            ).order_by('-effective_date').first()
            
            if current_grade_member and current_grade_member.salary_grade.id == new_grade.id:
                return JsonResponse({
                    'status': 'error',
                    'message': f'{user.name}さんは既に「{new_grade.name}」グレードです。'
                })
            
            with transaction.atomic():
                # 新しいグレード履歴を追加（履歴ベースなので終了処理は不要）
                
                # 新しいグレードを設定
                UserSalaryGrade.objects.create(
                    user=user,
                    salary_grade=new_grade,
                    effective_date=timezone.now().date(),
                    changed_by=request.user
                )
                
                # UserモデルにはSalaryGradeとのリレーションがpropertyなので、何もしない
                # current_salary_gradeはUserSalaryGradeの最新レコードから計算される
                
                # 管理者操作ログを記録
                AdminActionLog.objects.create(
                    admin_user=request.user,
                    action='grade_change',
                    target_user=user,
                    description=f'{user.name}さんのグレードを「{new_grade.name}」に変更しました'
                )
            
            return JsonResponse({
                'status': 'success',
                'message': f'{user.name}さんのグレードを「{new_grade.name}」に変更しました。'
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'status': 'error',
                'message': '無効なリクエストデータです。'
            })
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': f'処理中にエラーが発生しました: {str(e)}'
            })


# ======= 申告承認 =======
class AdminApplicationListView(AdminRequiredMixin, ListView):
    model = SkillApplication
    template_name = 'salary/admin/applications/list.html'
    context_object_name = 'applications'
    
    def get_queryset(self):
        return SkillApplication.objects.filter(status='pending').order_by('-application_date')


class AdminApplicationReviewView(AdminRequiredMixin, DetailView):
    model = SkillApplication
    template_name = 'salary/admin/applications/review.html'
    context_object_name = 'application'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        application = self.get_object()
        
        # 申告者の既存スキルを取得
        user_skills = UserSkill.objects.filter(
            user=application.user
        ).select_related('skill').order_by('-acquired_date')
        
        # 同じスキルの習得者を取得
        skill_holders = UserSkill.objects.filter(
            skill=application.skill
        ).select_related('user').order_by('-acquired_date')
        
        context.update({
            'user_skills': user_skills,
            'skill_holders': skill_holders,
        })
        return context


class AdminBulkApproveAPI(AdminRequiredMixin, View):
    @admin_required_api
    def post(self, request):
        try:
            data = json.loads(request.body)
            application_ids = data.get('application_ids', [])
            
            if not application_ids:
                return JsonResponse({
                    'status': 'error',
                    'message': '申告IDが指定されていません。'
                })
            
            approved_count = 0
            failed_applications = []
            
            with transaction.atomic():
                for app_id in application_ids:
                    try:
                        application = SkillApplication.objects.select_for_update().get(
                            id=app_id, status='pending'
                        )
                        
                        # 承認処理を実行
                        if self._approve_application(application, request.user):
                            approved_count += 1
                        else:
                            failed_applications.append(f"ID:{app_id}")
                            
                    except SkillApplication.DoesNotExist:
                        failed_applications.append(f"ID:{app_id}(見つからない)")
            
            if failed_applications:
                return JsonResponse({
                    'status': 'error',
                    'message': f'一部の処理に失敗しました: {", ".join(failed_applications)}'
                })
            
            return JsonResponse({
                'status': 'success',
                'message': f'{approved_count}件の申告を承認しました。'
            })
            
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': f'処理中にエラーが発生しました: {str(e)}'
            })
    
    def _approve_application(self, application, admin_user, comment=''):
        """申告を承認する共通処理"""
        try:
            # 既にスキルを習得していないかチェック
            if UserSkill.objects.filter(user=application.user, skill=application.skill).exists():
                return False
            
            # 申告のステータスを更新
            application.status = 'approved'
            application.processed_by = admin_user
            application.processed_date = timezone.now()
            application.save()
            
            # UserSkillレコードを作成
            UserSkill.objects.create(
                user=application.user,
                skill=application.skill,
                acquired_date=timezone.now().date(),
                approved_by=admin_user
            )
            
            # ログを記録
            AdminActionLog.objects.create(
                admin_user=admin_user,
                action='application_approve',
                target_user=application.user,
                description=f'スキル「{application.skill.name}」の申告を承認'
            )
            
            return True
            
        except Exception:
            return False


class AdminBulkRejectAPI(AdminRequiredMixin, View):
    @admin_required_api
    def post(self, request):
        try:
            data = json.loads(request.body)
            application_ids = data.get('application_ids', [])
            
            if not application_ids:
                return JsonResponse({
                    'status': 'error',
                    'message': '申告IDが指定されていません。'
                })
            
            rejected_count = 0
            failed_applications = []
            
            with transaction.atomic():
                for app_id in application_ids:
                    try:
                        application = SkillApplication.objects.select_for_update().get(
                            id=app_id, status='pending'
                        )
                        
                        # 却下処理を実行
                        if self._reject_application(application, request.user):
                            rejected_count += 1
                        else:
                            failed_applications.append(f"ID:{app_id}")
                            
                    except SkillApplication.DoesNotExist:
                        failed_applications.append(f"ID:{app_id}(見つからない)")
            
            if failed_applications:
                return JsonResponse({
                    'status': 'error',
                    'message': f'一部の処理に失敗しました: {", ".join(failed_applications)}'
                })
            
            return JsonResponse({
                'status': 'success',
                'message': f'{rejected_count}件の申告を却下しました。'
            })
            
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': f'処理中にエラーが発生しました: {str(e)}'
            })
    
    def _reject_application(self, application, admin_user, comment=''):
        """申告を却下する共通処理"""
        try:
            # 申告のステータスを更新
            application.status = 'rejected'
            application.processed_by = admin_user
            application.processed_date = timezone.now()
            application.save()
            
            # ログを記録
            AdminActionLog.objects.create(
                admin_user=admin_user,
                action='application_reject',
                target_user=application.user,
                description=f'スキル「{application.skill.name}」の申告を却下'
            )
            
            return True
            
        except Exception:
            return False


class AdminApproveApplicationAPI(AdminRequiredMixin, View):
    @admin_required_api
    def post(self, request, pk):
        try:
            data = json.loads(request.body)
            comment = data.get('comment', '').strip()
            
            application = get_object_or_404(
                SkillApplication, 
                id=pk, 
                status='pending'
            )
            
            with transaction.atomic():
                # 既にスキルを習得していないかチェック
                if UserSkill.objects.filter(user=application.user, skill=application.skill).exists():
                    return JsonResponse({
                        'status': 'error',
                        'message': 'このユーザーは既にこのスキルを習得しています。'
                    })
                
                # 申告のステータスを更新
                application.status = 'approved'
                application.processed_by = request.user
                application.processed_date = timezone.now()
                if comment:
                    application.comment = f"{application.comment}\n\n[承認者コメント]\n{comment}" if application.comment else f"[承認者コメント]\n{comment}"
                application.save()
                
                # UserSkillレコードを作成
                UserSkill.objects.create(
                    user=application.user,
                    skill=application.skill,
                    acquired_date=timezone.now().date(),
                    approved_by=request.user
                )
                
                # ログを記録
                AdminActionLog.objects.create(
                    admin_user=request.user,
                    action='application_approve',
                    target_user=application.user,
                    description=f'スキル「{application.skill.name}」の申告を承認'
                )
            
            return JsonResponse({
                'status': 'success',
                'message': f'{application.user.name}さんの「{application.skill.name}」スキル申告を承認しました。'
            })
            
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': f'承認処理中にエラーが発生しました: {str(e)}'
            })


class AdminRejectApplicationAPI(AdminRequiredMixin, View):
    @admin_required_api
    def post(self, request, pk):
        try:
            data = json.loads(request.body)
            comment = data.get('comment', '').strip()
            
            application = get_object_or_404(
                SkillApplication,
                id=pk,
                status='pending'
            )
            
            with transaction.atomic():
                # 申告のステータスを更新
                application.status = 'rejected'
                application.processed_by = request.user
                application.processed_date = timezone.now()
                if comment:
                    application.comment = f"{application.comment}\n\n[却下理由]\n{comment}" if application.comment else f"[却下理由]\n{comment}"
                application.save()
                
                # ログを記録
                AdminActionLog.objects.create(
                    admin_user=request.user,
                    action='application_reject',
                    target_user=application.user,
                    description=f'スキル「{application.skill.name}」の申告を却下'
                )
            
            return JsonResponse({
                'status': 'success',
                'message': f'{application.user.name}さんの「{application.skill.name}」スキル申告を却下しました。'
            })
            
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': f'却下処理中にエラーが発生しました: {str(e)}'
            })