from django.contrib import admin
from django.utils import timezone
from .models import Skill, SalaryGrade, UserSkill, SkillApplication, UserSalaryGrade


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'created_at')
    list_filter = ('category', 'created_at')
    search_fields = ('name', 'description')
    ordering = ('category', 'name')


@admin.register(SalaryGrade)
class SalaryGradeAdmin(admin.ModelAdmin):
    list_display = ('name', 'level', 'hourly_wage', 'required_skills_count', 'next_grades_count')
    list_filter = ('level',)
    search_fields = ('name',)
    ordering = ('level', 'name')
    filter_horizontal = ('required_skills', 'next_possible_grades')
    
    def required_skills_count(self, obj):
        return obj.required_skills.count()
    required_skills_count.short_description = '必要スキル数'
    
    def next_grades_count(self, obj):
        return obj.next_possible_grades.count()
    next_grades_count.short_description = '次昇進先数'
    
    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "next_possible_grades":
            # 編集時に自分自身を除外
            if hasattr(request, '_obj_'):
                kwargs["queryset"] = SalaryGrade.objects.exclude(pk=request._obj_.pk)
        return super().formfield_for_manytomany(db_field, request, **kwargs)
    
    def get_form(self, request, obj=None, **kwargs):
        # objを後でformfield_for_manytomanyで使用するために保存
        request._obj_ = obj
        return super().get_form(request, obj, **kwargs)


@admin.register(UserSkill)
class UserSkillAdmin(admin.ModelAdmin):
    list_display = ('user', 'skill', 'acquired_date', 'approved_by')
    list_filter = ('skill__category', 'acquired_date', 'approved_by')
    search_fields = ('user__name', 'skill__name')
    ordering = ('-acquired_date',)
    autocomplete_fields = ('user', 'skill')
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "approved_by":
            # is_staffのユーザーのみを選択肢に表示
            kwargs["queryset"] = db_field.related_model.objects.filter(is_staff=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(SkillApplication)
class SkillApplicationAdmin(admin.ModelAdmin):
    list_display = ('user', 'skill', 'status', 'application_date', 'processed_by')
    list_filter = ('status', 'skill__category', 'application_date')
    search_fields = ('user__name', 'skill__name')
    ordering = ('-application_date',)
    autocomplete_fields = ('user', 'skill')
    readonly_fields = ('application_date',)
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "processed_by":
            # is_staffのユーザーのみを選択肢に表示
            kwargs["queryset"] = db_field.related_model.objects.filter(is_staff=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    actions = ['approve_applications', 'reject_applications']
    
    def approve_applications(self, request, queryset):
        for application in queryset.filter(status='pending'):
            application.status = 'approved'
            application.processed_by = request.user
            application.processed_date = timezone.now()
            application.save()
            
            # UserSkillレコードを作成
            UserSkill.objects.get_or_create(
                user=application.user,
                skill=application.skill,
                defaults={
                    'acquired_date': timezone.now().date(),
                    'approved_by': request.user,
                }
            )
        self.message_user(request, f"{queryset.count()}件の申告を承認しました。")
    approve_applications.short_description = "選択した申告を承認する"
    
    def reject_applications(self, request, queryset):
        for application in queryset.filter(status='pending'):
            application.status = 'rejected'
            application.processed_by = request.user
            application.processed_date = timezone.now()
            application.save()
        self.message_user(request, f"{queryset.count()}件の申告を却下しました。")
    reject_applications.short_description = "選択した申告を却下する"


@admin.register(UserSalaryGrade)
class UserSalaryGradeAdmin(admin.ModelAdmin):
    list_display = ('user', 'salary_grade', 'effective_date', 'changed_by')
    list_filter = ('salary_grade__level', 'effective_date', 'changed_by')
    search_fields = ('user__name', 'salary_grade__name')
    ordering = ('-effective_date',)
    autocomplete_fields = ('user', 'salary_grade')
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "changed_by":
            # is_staffのユーザーのみを選択肢に表示
            kwargs["queryset"] = db_field.related_model.objects.filter(is_staff=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    def save_model(self, request, obj, form, change):
        if not obj.changed_by:
            obj.changed_by = request.user
        super().save_model(request, obj, form, change)
