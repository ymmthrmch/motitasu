from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Skill(models.Model):
    """スキルマスタ"""
    CATEGORY_CHOICES = [
        ('technical', '技術スキル'),
        ('customer_service', '接客スキル'),
        ('management', '管理スキル'),
    ]
    
    name = models.CharField(max_length=100, verbose_name='スキル名')
    description = models.TextField(verbose_name='説明')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, verbose_name='スキルカテゴリ')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'スキル'
        verbose_name_plural = 'スキル'
        ordering = ['category', 'name']

    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"


class SalaryGrade(models.Model):
    """給与グレードマスタ"""
    name = models.CharField(max_length=50, verbose_name='グレード名')
    hourly_wage = models.DecimalField(max_digits=6, decimal_places=0, verbose_name='時給')
    level = models.IntegerField(verbose_name='レベル')  # unique=False: 同レベルに複数グレード可能
    description = models.TextField(
        verbose_name='説明',
        default=''
        )
    required_skills = models.ManyToManyField(Skill, blank=True, verbose_name='必要習得スキル')
    next_possible_grades = models.ManyToManyField(
        'self', blank=True, symmetrical=False,
        verbose_name='次に昇進可能なグレード',
        help_text='このグレードから昇進可能な次のグレードを選択してください'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = '給与グレード'
        verbose_name_plural = '給与グレード'
        ordering = ['level', 'name']

    def __str__(self):
        return f"{self.name} (レベル{self.level}、時給{self.hourly_wage}円)"
    
    def clean(self):
        super().clean()
        # 自分自身を次の昇進先に設定することを防ぐ
        if self.pk and self in self.next_possible_grades.all():
            from django.core.exceptions import ValidationError
            raise ValidationError({
                'next_possible_grades': '自分自身を次の昇進先に設定することはできません。'
            })


class UserSkill(models.Model):
    """ユーザー習得スキル"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='ユーザー')
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, verbose_name='スキル')  # CASCADE: スキル削除時に習得記録も削除
    acquired_date = models.DateField(verbose_name='習得日')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='approved_skills', verbose_name='承認者')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'ユーザー習得スキル'
        verbose_name_plural = 'ユーザー習得スキル'
        unique_together = ['user', 'skill']
        ordering = ['user', 'skill']

    def __str__(self):
        return f"{self.user.name} - {self.skill.name}"
    
    def clean(self):
        super().clean()
        # 承認者はis_staffのユーザーのみ
        if self.approved_by and not self.approved_by.is_staff:
            from django.core.exceptions import ValidationError
            raise ValidationError({
                'approved_by': 'スキル承認者は管理者権限（is_staff）を持つユーザーである必要があります。'
            })


class SkillApplication(models.Model):
    """スキル習得申告"""
    STATUS_CHOICES = [
        ('pending', '承認待ち'),
        ('approved', '承認済み'),
        ('rejected', '却下'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='ユーザー')
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, verbose_name='スキル')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='ステータス')
    application_date = models.DateTimeField(auto_now_add=True, verbose_name='申告日')
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='processed_applications', verbose_name='処理者')
    processed_date = models.DateTimeField(null=True, blank=True, verbose_name='処理日')
    comment = models.TextField(blank=True, verbose_name='申告理由・処理コメント')

    class Meta:
        verbose_name = 'スキル習得申告'
        verbose_name_plural = 'スキル習得申告'
        ordering = ['-application_date']

    def __str__(self):
        return f"{self.user.name} - {self.skill.name} ({self.get_status_display()})"
    
    def clean(self):
        super().clean()
        # 処理者はis_staffのユーザーのみ
        if self.processed_by and not self.processed_by.is_staff:
            from django.core.exceptions import ValidationError
            raise ValidationError({
                'processed_by': 'スキル申告の処理者は管理者権限（is_staff）を持つユーザーである必要があります。'
            })


class UserSalaryGrade(models.Model):
    """ユーザーの給与グレード履歴"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='salary_history', verbose_name='ユーザー')
    salary_grade = models.ForeignKey(SalaryGrade, on_delete=models.PROTECT, verbose_name='給与グレード')
    effective_date = models.DateField(verbose_name='適用日')
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='salary_changes_made', verbose_name='変更者')
    reason = models.TextField(blank=True, verbose_name='変更理由')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'ユーザー給与グレード履歴'
        verbose_name_plural = 'ユーザー給与グレード履歴'
        ordering = ['-effective_date']
        indexes = [
            models.Index(fields=['user', '-effective_date']),
        ]

    def __str__(self):
        return f"{self.user.name} - {self.salary_grade.name} ({self.effective_date})"
    
    def clean(self):
        super().clean()
        # 変更者はis_staffのユーザーのみ
        if self.changed_by and not self.changed_by.is_staff:
            from django.core.exceptions import ValidationError
            raise ValidationError({
                'changed_by': '給与グレード変更者は管理者権限（is_staff）を持つユーザーである必要があります。'
            })


class AdminActionLog(models.Model):
    """管理者操作ログ"""
    ACTION_CHOICES = [
        ('skill_create', 'スキル作成'),
        ('skill_edit', 'スキル編集'),
        ('skill_grant', 'スキル手動付与'),
        ('skill_revoke', 'スキル取り消し'),
        ('grade_create', 'グレード作成'),
        ('grade_edit', 'グレード編集'),
        ('grade_change', 'ユーザーグレード変更'),
        ('application_approve', '申告承認'),
        ('application_reject', '申告却下'),
    ]

    admin_user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='操作者')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, verbose_name='操作種別')
    target_user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        related_name='admin_actions_received',
        null=True, 
        blank=True,
        verbose_name='対象ユーザー'
    )
    description = models.TextField(verbose_name='操作内容')
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name='実行日時')

    class Meta:
        verbose_name = '管理者操作ログ'
        verbose_name_plural = '管理者操作ログ'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['admin_user', '-timestamp']),
        ]

    def __str__(self):
        return f"{self.admin_user.name} - {self.get_action_display()} ({self.timestamp.strftime('%Y-%m-%d %H:%M')})"
