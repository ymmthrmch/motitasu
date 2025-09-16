from django.db import models
from django.core.exceptions import ValidationError

class LeaderboardEntry(models.Model):
    """
    リーダーボードへの参加記録と成績を管理
    月ごとの参加状況と労働時間、順位を一元管理
    """
    user = models.ForeignKey('accounts.User', on_delete=models.CASCADE)
    year = models.PositiveIntegerField()
    month = models.PositiveIntegerField()
    joined_at = models.DateTimeField(auto_now_add=True)

    total_minutes = models.DecimalField(
        max_digits=6, decimal_places=2, default=0
    )
    rank = models.IntegerField(null=True, blank=True)
    last_updated = models.DateTimeField(auto_now=True)

    cached_daily_minutes = models.JSONField(
        default=dict, blank=True,
        help_text="{'1': 480, '2': 420, ...} 形式で保存"
    )
    rank = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        unique_together = ('user', 'year', 'month')
        ordering = ['rank', '-total_hours']
        indexes = [
            models.Index(fields=['user', 'year', 'month']),
        ]

    def clean(self):
        super().clean()
        if not (1 <= self.month <= 12):
            raise ValidationError('月は1から12の間でなければなりません。')

    def __str__(self):
        return f"{self.user.username} - {self.year}/{self.month} - Rank: {self.rank}"
    
    @property
    def total_hours_display(self):
        hours = self.total_minutes // 60
        minutes = self.total_minutes % 60
        return f"{hours}時間{minutes}分"