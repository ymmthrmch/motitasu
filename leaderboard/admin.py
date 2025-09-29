from django.contrib import admin
from .models import LeaderboardEntry


@admin.register(LeaderboardEntry)
class LeaderboardEntryAdmin(admin.ModelAdmin):
    """ランキングエントリの管理画面設定"""
    
    list_display = (
        'user', 'year', 'month', 'rank', 'total_minutes', 
        'total_hours_display', 'joined_at', 'last_updated'
    )
    
    list_filter = (
        'year', 'month', 'rank', 'joined_at', 'last_updated'
    )
    
    search_fields = (
        'user__name', 'user__email'
    )
    
    ordering = ('year', 'month', 'rank')
    
    readonly_fields = (
        'joined_at', 'last_updated', 'total_hours_display'
    )
    
    fieldsets = (
        ('基本情報', {
            'fields': ('user', 'year', 'month')
        }),
        ('ランキング情報', {
            'fields': ('rank', 'total_minutes', 'total_hours_display')
        }),
        ('キャッシュデータ', {
            'fields': ('cached_daily_minutes',),
            'classes': ('collapse',),
            'description': '日別労働時間のキャッシュデータ（JSON形式）'
        }),
        ('タイムスタンプ', {
            'fields': ('joined_at', 'last_updated'),
            'classes': ('collapse',),
        })
    )
    
    # 一覧ページでの表示件数
    list_per_page = 25
    
    # 年月での絞り込みを簡単にするアクション
    actions = ['recalculate_rankings', 'recalculate_from_scratch']
    
    def recalculate_rankings(self, request, queryset):
        """選択されたエントリの年月でランキングを再計算"""
        from .services import LeaderboardService
        
        updated_count = 0
        year_months = set()
        
        for entry in queryset:
            year_months.add((entry.year, entry.month))
        
        service = LeaderboardService()
        for year, month in year_months:
            result = service.update_leaderboard(year, month)
            if result.get('success'):
                # 該当年月のエントリ数をカウント
                count = LeaderboardEntry.objects.filter(year=year, month=month).count()
                updated_count += count
        
        self.message_user(
            request,
            f'{len(year_months)}年月のランキングを再計算しました（{updated_count}件のエントリを更新）'
        )
    
    recalculate_rankings.short_description = '選択した年月のランキングを再計算'
    
    def recalculate_from_scratch(self, request, queryset):
        """選択されたエントリをキャッシュを使わずに完全再計算"""
        from .services.leaderboard_service import LeaderboardService
        
        success_count = 0
        error_count = 0
        year_months = set()
        
        for entry in queryset:
            service = LeaderboardService(entry.user)
            result_entry, response = service.recalculate_user_stats_from_scratch(
                year=entry.year, 
                month=entry.month
            )
            
            if response and response.get('success'):
                success_count += 1
                year_months.add((entry.year, entry.month))
            else:
                error_count += 1
        
        # 関係する年月のランキングも更新
        service = LeaderboardService()
        for year, month in year_months:
            service.update_leaderboard(year, month)
        
        if error_count == 0:
            self.message_user(
                request,
                f'{success_count}件のエントリを完全再計算しました。ランキングも更新されました。'
            )
        else:
            self.message_user(
                request,
                f'完了: {success_count}件成功、{error_count}件失敗',
                level='WARNING'
            )
    
    recalculate_from_scratch.short_description = '選択したエントリを完全再計算（キャッシュリセット）'
    
    # カスタムクエリセット（パフォーマンス最適化）
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')
    
    # ユーザー名での表示をカスタマイズ
    def get_user_display(self, obj):
        return f"{obj.user.name} ({obj.user.name})"
    get_user_display.short_description = 'ユーザー'
