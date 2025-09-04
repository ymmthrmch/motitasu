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
    
    objects = UserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['name']
    
    class Meta:
        verbose_name = 'ユーザー'
        verbose_name_plural = 'ユーザー'
        db_table = 'users'
    
    def __str__(self):
        return self.name