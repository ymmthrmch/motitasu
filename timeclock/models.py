from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
import pytz

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
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['user', 'clock_type', 'timestamp']),
        ]
    
    def save(self, *args, **kwargs):
        if not self.timestamp:
            jst = pytz.timezone('Asia/Tokyo')
            self.timestamp = timezone.now().astimezone(jst)
        
        self.clean()
        super().save(*args, **kwargs)
    
    def clean(self):
        if not self.user_id:
            return
        
        jst = pytz.timezone('Asia/Tokyo')
        today_start = timezone.now().astimezone(jst).replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timezone.timedelta(days=1)
        
        today_records = TimeRecord.objects.filter(
            user=self.user,
            timestamp__gte=today_start,
            timestamp__lt=today_end
        ).exclude(pk=self.pk).order_by('timestamp')
        
        last_record = today_records.last()
        
        if self.clock_type == 'clock_in':
            if today_records.filter(clock_type='clock_in').exists():
                raise ValidationError('本日の出勤は既に打刻されています。')
            if last_record:
                raise ValidationError('出勤は一日の最初の打刻である必要があります。')
        
        elif self.clock_type == 'clock_out':
            if not today_records.filter(clock_type='clock_in').exists():
                raise ValidationError('出勤していないため退勤できません。')
            if today_records.filter(clock_type='clock_out').exists():
                raise ValidationError('本日の退勤は既に打刻されています。')
            if last_record and last_record.clock_type == 'break_start':
                raise ValidationError('休憩中は退勤できません。先に休憩を終了してください。')
        
        elif self.clock_type == 'break_start':
            if not today_records.filter(clock_type='clock_in').exists():
                raise ValidationError('出勤していないため休憩を開始できません。')
            if today_records.filter(clock_type='clock_out').exists():
                raise ValidationError('退勤後は休憩を開始できません。')
            if last_record and last_record.clock_type == 'break_start':
                raise ValidationError('既に休憩中です。')
        
        elif self.clock_type == 'break_end':
            if not last_record or last_record.clock_type != 'break_start':
                raise ValidationError('休憩を開始していないため終了できません。')
    
    def __str__(self):
        jst = pytz.timezone('Asia/Tokyo')
        timestamp_jst = self.timestamp.astimezone(jst)
        return f"{self.user.name} - {self.get_clock_type_display()} - {timestamp_jst.strftime('%Y-%m-%d %H:%M:%S')}"
