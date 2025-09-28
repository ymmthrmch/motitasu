from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models


class UserManager(BaseUserManager):
    def create_user(self, email, name, password=None):
        if not email:
            raise ValueError('メールアドレスは必須です。')
        
        email = self.normalize_email(email)
        user = self.model(email=email, name=name)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_staff(self, email, name, password=None):
        user = self.create_user(email, name, password)
        user.is_staff = True
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, name, password=None):
        user = self.create_user(email, name, password)
        user.is_staff = True
        user.is_superuser = True
        user.save(using=self._db)
        return user


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(
        verbose_name='メールアドレス',
        max_length=255,
        unique=True,
    )
    name = models.CharField(
        verbose_name='名前',
        max_length=100,
    )
    is_staff = models.BooleanField(
        verbose_name='管理者権限',
        default=False,
        help_text='管理サイトにログインできるかどうかを指定します。',
    )
    is_active = models.BooleanField(
        verbose_name='アクティブ',
        default=True,
    )
    created_at = models.DateTimeField(
        verbose_name='作成日',
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        verbose_name='更新日',
        auto_now=True,
    )
    hourly_wage = models.PositiveIntegerField(
        verbose_name='時給',
        null=True,
        blank=True,
        help_text='ユーザーの時給を設定します（任意）。',
    )
    hire_date = models.DateField(
        verbose_name='雇用開始日',
        null=True,
        blank=True,
        help_text='有給休暇計算の基準日となります。',
    )
    weekly_work_days = models.PositiveIntegerField(
        verbose_name='週の所定労働日数',
        default=5,
        help_text='週の所定労働日数（1-7日）。有給休暇の付与日数計算に使用します。',
    )
    current_paid_leave = models.PositiveIntegerField(
        verbose_name='現在の有給休暇日数',
        default=0,
        help_text='現在付与されている有給休暇の残日数。',
    )
    paid_leave_grant_schedule = models.JSONField(
        verbose_name='有給休暇付与スケジュール',
        default=list,
        blank=True,
        help_text='有給休暇の付与日リスト。["YYYY-MM-DD", ...] の形式。入社日に基づいて自動計算されます。',
    )
    
    objects = UserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['name']
    
    class Meta:
        verbose_name = 'ユーザー'
        verbose_name_plural = 'ユーザー'
        db_table = 'users'
    
    def __str__(self):
        return self.name
    
    def clean(self):
        cleaned_data = super().clean()
        if self.weekly_work_days < 1 or self.weekly_work_days > 7:
            raise ValueError('週の所定労働日数は1から7の間で指定してください。')
        return cleaned_data
    
    def save(self, *args, **kwargs):
        """
        Userモデルのsaveメソッドをオーバーライド
        
        Rules:
            - hire_dateが変更された場合、paid_leave_grant_scheduleを自動更新
            - 入社日から全ての付与日を計算（1回目〜20回目程度）
            - super().save()を呼び出してデータベースに保存
        """
        # 入社日が変更された場合、付与スケジュールを自動更新
        if self.hire_date:
            # 既存データの場合、hire_dateが変更されたかチェック
            if self.pk:
                try:
                    old_instance = User.objects.get(pk=self.pk)
                    if old_instance.hire_date != self.hire_date:
                        self.paid_leave_grant_schedule = self._calculate_grant_schedule()
                except User.DoesNotExist:
                    pass
            else:
                # 新規作成の場合
                self.paid_leave_grant_schedule = self._calculate_grant_schedule()
        
        super().save(*args, **kwargs)
    
    def _calculate_grant_schedule(self):
        """
        入社日に基づいて付与スケジュールを計算（内部メソッド）
        
        Returns:
            list[date]: 付与日のリスト
            
        Rules:
            - PaidLeaveCalculatorを使用して各回の付与日を計算
            - 1回目〜20回目程度の付与日を事前計算
        """
        if not self.hire_date:
            return []
        
        # 循環インポートを避けるため、ここでインポート
        from timeclock.services.paid_leave_calculator import PaidLeaveCalculator
        
        calculator = PaidLeaveCalculator(self)
        schedule = []
        
        # 20回分の付与日を計算（十分な期間をカバー）
        for grant_count in range(1, 21):
            try:
                grant_date = calculator.calculate_grant_date(grant_count)
                schedule.append(grant_date.isoformat())
            except Exception:
                # 計算エラーが発生した場合はそこで終了
                break
        
        return schedule
    
    def get_latest_grant_date(self, reference_date=None):
        """
        指定日時点での直近の付与日を取得
        
        Args:
            reference_date: 基準日（Noneの場合は今日）
            
        Returns:
            Optional[date]: 直近の付与日（まだ付与日がない場合はNone）
            
        Rules:
            - self.paid_leave_grant_scheduleから基準日以前の最新付与日を取得
            - シグナル処理での判定に使用
        """
        from datetime import date
        
        if reference_date is None:
            reference_date = date.today()
        
        if isinstance(reference_date, str):
            reference_date_str = reference_date
        else:
            reference_date_str = reference_date.isoformat()
        
        latest_date_str = None
        
        for grant_date_str in self.paid_leave_grant_schedule:
            if grant_date_str <= reference_date_str:
                if latest_date_str is None or grant_date_str > latest_date_str:
                    latest_date_str = grant_date_str
        
        if latest_date_str:
            year, month, day = map(int, latest_date_str.split('-'))
            return date(year, month, day)
        
        return None
    
    def is_grant_date_today(self, target_date):
        """
        指定日がこのユーザーの付与日かを判定
        
        Args:
            target_date: 判定対象日
            
        Returns:
            bool: 付与日の場合True
            
        Rules:
            - self.paid_leave_grant_scheduleフィールドを参照
            - 日次処理での対象者判定に使用
        """
        from datetime import date
        
        if isinstance(target_date, str):
            target_date_str = target_date
        elif isinstance(target_date, date):
            target_date_str = target_date.isoformat()
        else:
            return False
        
        return target_date_str in self.paid_leave_grant_schedule
    
    @property
    def current_salary_grade(self):
        """現在の給与グレード（最新のUserSalaryGradeから取得）"""
        latest_grade = self.salary_history.order_by('-effective_date').first()
        return latest_grade.salary_grade if latest_grade else None
    
    @property
    def current_hourly_wage(self):
        """現在の時給（給与グレードから取得、設定されていない場合はNone）"""
        current_grade = self.current_salary_grade
        if current_grade:
            return current_grade.hourly_wage
        return None