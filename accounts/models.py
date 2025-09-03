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
    
    objects = UserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['name']
    
    class Meta:
        verbose_name = 'ユーザー'
        verbose_name_plural = 'ユーザー'
        db_table = 'users'
    
    def __str__(self):
        return self.name