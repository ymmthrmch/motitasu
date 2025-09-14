from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Count
from datetime import timedelta
import pytz

User = get_user_model()

class Message(models.Model):
    """伝言板メッセージ"""
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='messages',
        verbose_name='投稿者'
    )
    content = models.TextField(
        verbose_name='メッセージ内容',
        max_length=200,
        help_text='メッセージ内容を入力してください（最大200文字）'
    )
    is_pinned = models.BooleanField(
        verbose_name='ピン留め',
        default=False,
        help_text='このメッセージがピン留めされているかどうか'
    )
    pin_duration_hours = models.PositiveIntegerField(
        verbose_name='ピン留め期間（時間）',
        null=True,
        blank=True,
        choices=[
            (12, '12時間'),
            (24, '24時間'),
            (168, '1週間'),  # 7日 × 24時間 = 168時間
        ],
        help_text='ピン留め期間を時間単位で指定'
    )
    pinned_at = models.DateTimeField(
        verbose_name='ピン留め日時',
        null=True,
        blank=True,
        help_text='ピン留めされた日時'
    )
    pin_expires_at = models.DateTimeField(
        verbose_name='ピン留め期限',
        null=True,
        blank=True,
        help_text='ピン留めが自動解除される日時'
    )
    created_at = models.DateTimeField(
        verbose_name='投稿日時',
        auto_now_add=True
    )
    updated_at = models.DateTimeField(
        verbose_name='更新日時',
        auto_now=True
    )
    
    class Meta:
        verbose_name = 'メッセージ'
        verbose_name_plural = 'メッセージ'
        ordering = [
            '-is_pinned',  # ピン留めメッセージを上位に
            '-pin_duration_hours',  # ピン留め期間が長い順
            '-pinned_at',  # ピン留め日時が新しい順
            '-created_at'  # 通常の投稿日時順
        ]
        
    def __str__(self):
        return f"{self.user.name}: {self.content[:50]}..."
        
    def get_reaction_counts(self):
        """各リアクションの数を取得"""
        return self.reactions.values('reaction_type').annotate(count=Count('reaction_type'))
        
    def is_pin_expired(self):
        """ピン留めが期限切れかどうかを判定"""
        if not self.is_pinned or not self.pin_expires_at:
            return False
        jst = pytz.timezone('Asia/Tokyo')
        return timezone.now().astimezone(jst) > self.pin_expires_at
        
    def pin_message(self, duration_hours):
        """メッセージをピン留めする"""
        jst = pytz.timezone('Asia/Tokyo')
        self.is_pinned = True
        self.pin_duration_hours = duration_hours
        self.pinned_at = timezone.now().astimezone(jst)
        self.pin_expires_at = self.pinned_at + timedelta(hours=duration_hours)
        self.save()
        
    def unpin_message(self):
        """ピン留めを解除する"""
        self.is_pinned = False
        self.pin_duration_hours = None
        self.pinned_at = None
        self.pin_expires_at = None
        self.save()
        
    def get_pin_remaining_time(self):
        """ピン留めの残り時間を取得（秒単位）"""
        if not self.is_pinned or not self.pin_expires_at:
            return 0
        jst = pytz.timezone('Asia/Tokyo')
        remaining = self.pin_expires_at - timezone.now().astimezone(jst)
        return max(0, remaining.total_seconds())


class Reaction(models.Model):
    """メッセージリアクション"""
    
    REACTION_CHOICES = [
        ('thumbs_up', '👍'),
        ('heart', '❤️'),
        ('laughing', '😂'),
        ('surprised', '😮'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='reactions',
        verbose_name='リアクションユーザー'
    )
    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name='reactions',
        verbose_name='対象メッセージ'
    )
    reaction_type = models.CharField(
        max_length=20,
        choices=REACTION_CHOICES,
        verbose_name='リアクション種類'
    )
    created_at = models.DateTimeField(
        verbose_name='リアクション日時',
        auto_now_add=True
    )
    
    class Meta:
        verbose_name = 'リアクション'
        verbose_name_plural = 'リアクション'
        unique_together = ('user', 'message', 'reaction_type')  # 同一ユーザー・同一メッセージ・同一種類の重複防止
        ordering = ['-created_at']
        
    def __str__(self):
        return f"{self.user.name} → {self.get_reaction_type_display()} → {self.message.content[:30]}"
        
    def get_emoji(self):
        """絵文字を取得"""
        return dict(self.REACTION_CHOICES)[self.reaction_type]