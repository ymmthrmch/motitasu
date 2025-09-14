from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.conf import settings
from datetime import timedelta
from zoneinfo import ZoneInfo

User = get_user_model()

class TimeRecord(models.Model):
    CLOCK_TYPE_CHOICES = [
        ('clock_in', '出勤'),
        ('clock_out', '退勤'),
        ('break_start', '休憩開始'),
        ('break_end', '休憩終了'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='time_records')
    clock_type = models.CharField(max_length=20, choices=CLOCK_TYPE_CHOICES)
    timestamp = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = '打刻記録'
        verbose_name_plural = '打刻記録'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['user', 'clock_type', 'timestamp']),
        ]
    
    def save(self, *args, **kwargs):
        if not self.timestamp:
            self.timestamp = timezone.now()
        
        self.clean()
        super().save(*args, **kwargs)
    
    def clean(self):
        if not self.user_id:
            return
        
        jst = ZoneInfo(settings.TIME_ZONE)
        
        if self.timestamp:
            record_time = self.timestamp
            if timezone.is_naive(record_time):
                record_time = record_time.replace(tzinfo=jst)
            else:
                record_time = record_time.astimezone(jst)
        else:
            record_time = timezone.now().astimezone(jst)
        
        day_start = record_time.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        
        day_records = TimeRecord.objects.filter(
            user=self.user,
            timestamp__gte=day_start,
            timestamp__lt=day_end
        ).exclude(pk=self.pk).order_by('timestamp')
        
        last_record = day_records.filter(timestamp__lte=self.timestamp).last()
        
        if self.clock_type == 'clock_in':
            if day_records.filter(clock_type='clock_in').exists():
                raise ValidationError('この日の出勤は既に打刻されています。')
            if last_record:
                raise ValidationError('出勤は一日の最初の打刻である必要があります。')
        
        elif self.clock_type == 'clock_out':
            if not day_records.filter(clock_type='clock_in', timestamp__lte=self.timestamp).exists():
                raise ValidationError('出勤後でないため退勤できません。')
            if day_records.filter(clock_type='clock_out').exists():
                raise ValidationError('この日の退勤は既に打刻されています。')
            if last_record and last_record.clock_type == 'break_start':
                raise ValidationError('休憩中は退勤できません。先に休憩を終了してください。')
        
        elif self.clock_type == 'break_start':
            if not day_records.filter(clock_type='clock_in', timestamp__lte=self.timestamp).exists():
                raise ValidationError('出勤していないため休憩を開始できません。')
            if day_records.filter(clock_type='clock_out', timestamp__lte=self.timestamp).exists():
                raise ValidationError('退勤後は休憩を開始できません。')
            if last_record and last_record.clock_type == 'break_start':
                raise ValidationError('既に休憩中です。')
        
        elif self.clock_type == 'break_end':
            if not last_record or last_record.clock_type != 'break_start':
                raise ValidationError('休憩を開始していないため終了できません。')
    
    def __str__(self):
        jst = ZoneInfo(settings.TIME_ZONE)
        timestamp_jst = self.timestamp.astimezone(jst)
        return f"{self.user.name} - {self.get_clock_type_display()} - {timestamp_jst.strftime('%Y-%m-%d %H:%M:%S')}"


class MonthlyTarget(models.Model):
    """月ごとの目標収入を管理するモデル"""
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='monthly_targets',
        verbose_name='ユーザー'
    )
    year = models.PositiveIntegerField(
        verbose_name='年'
    )
    month = models.PositiveIntegerField(
        verbose_name='月',
        choices=[(i, f'{i}月') for i in range(1, 13)]
    )
    target_income = models.PositiveIntegerField(
        verbose_name='目標月収',
        help_text='この月の目標月収を設定します。'
    )
    created_at = models.DateTimeField(
        verbose_name='作成日',
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        verbose_name='更新日',
        auto_now=True,
    )
    
    class Meta:
        verbose_name = '月別目標'
        verbose_name_plural = '月別目標'
        unique_together = ('user', 'year', 'month')
        ordering = ['-year', '-month']
    
    def __str__(self):
        return f"{self.user.name} - {self.year}年{self.month}月 - {self.target_income:,}円"


class PaidLeaveRecord(models.Model):
    """有給休暇の付与・使用記録"""
    RECORD_TYPE_CHOICES = [
        ('grant', '付与'),
        ('use', '使用'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='paid_leave_records',
        verbose_name='ユーザー'
    )
    record_type = models.CharField(
        max_length=10,
        choices=RECORD_TYPE_CHOICES,
        verbose_name='記録タイプ'
    )
    days = models.PositiveIntegerField(
        verbose_name='日数'
    )
    grant_date = models.DateField(
        verbose_name='付与日',
        help_text='付与された日付（使用時は付与された日を記録）'
    )
    expiry_date = models.DateField(
        verbose_name='有効期限',
        help_text='この有給休暇の有効期限（付与日から2年後）'
    )
    used_date = models.DateField(
        verbose_name='使用日',
        null=True,
        blank=True,
        help_text='有給休暇を使用した日（付与・取消・時効消滅時はNull）'
    )
    expired = models.BooleanField(
        verbose_name='時効フラグ',
        default=False,
        help_text='この記録が時効により無効化されている場合True'
    )
    description = models.CharField(
        max_length=255,
        verbose_name='備考',
        blank=True,
        help_text='付与理由や使用理由などの備考'
    )
    created_at = models.DateTimeField(
        verbose_name='作成日',
        auto_now_add=True,
    )
    
    class Meta:
        verbose_name = '有給休暇記録'
        verbose_name_plural = '有給休暇記録'
        ordering = ['-grant_date', '-created_at']
    
    def __str__(self):
        return f"{self.user.name} - {self.get_record_type_display()} {self.days}日 ({self.grant_date})"
