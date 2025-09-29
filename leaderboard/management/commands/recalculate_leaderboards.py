"""
ランキングデータ完全再計算コマンド（定期処理用）
"""

from django.core.management.base import BaseCommand
from datetime import date, datetime
from django.conf import settings
from django.utils import timezone
from zoneinfo import ZoneInfo
import logging

from leaderboard.models import LeaderboardEntry
from leaderboard.services.leaderboard_service import LeaderboardService


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """ランキングデータ完全再計算コマンド（定期処理用）"""
    
    help = '指定年月のランキングデータを完全再計算します'
    
    def add_arguments(self, parser):
        """コマンド引数の定義"""
        parser.add_argument(
            '--year',
            type=int,
            help='処理対象年（未指定の場合は現在年）',
            default=None
        )
        parser.add_argument(
            '--month',
            type=int,
            help='処理対象月（未指定の場合は現在月）',
            default=None
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='実際の処理は実行せず、対象エントリのみを表示',
            default=False
        )
    
    def handle(self, *args, **options):
        """
        実行内容:
            1. 指定年月の全ランキングエントリを完全再計算
            2. キャッシュデータをリセットして月初から計算し直し
            3. ランキングを更新
        """
        # 処理対象年月の決定
        if options['year'] and options['month']:
            target_year = options['year']
            target_month = options['month']
        else:
            # JST基準で現在の年月を取得
            jst = ZoneInfo(settings.TIME_ZONE)
            now = timezone.now().astimezone(jst)
            target_year = options['year'] or now.year
            target_month = options['month'] or now.month
        
        # 月の範囲チェック
        if not (1 <= target_month <= 12):
            self.stdout.write(
                self.style.ERROR(f'無効な月です: {target_month} (1-12の範囲で指定してください)')
            )
            return
        
        self.stdout.write(f'ランキングデータ完全再計算を開始します (対象: {target_year}年{target_month}月)')
        logger.info(f'ランキングデータ完全再計算を開始: 対象={target_year}年{target_month}月')
        
        if options['dry_run']:
            self.stdout.write(self.style.WARNING('DRY-RUN モード: 実際の処理は実行されません'))
        
        try:
            # 対象年月のエントリを取得
            entries = LeaderboardEntry.objects.filter(
                year=target_year,
                month=target_month
            ).select_related('user')
            
            if options['dry_run']:
                # DRY-RUNモード: 対象エントリのみ表示
                self._dry_run_check(entries, target_year, target_month)
            else:
                # 実際の処理を実行
                self._execute_recalculation(entries, target_year, target_month)
            
        except Exception as e:
            error_msg = f'処理中にエラーが発生しました: {e}'
            self.stdout.write(self.style.ERROR(error_msg))
            logger.error(error_msg, exc_info=True)
            raise
    
    def _dry_run_check(self, entries, target_year, target_month):
        """DRY-RUN: 処理対象エントリをチェック"""
        if entries:
            self.stdout.write(f'再計算対象エントリ数: {len(entries)}')
            for entry in entries:
                self.stdout.write(
                    f'  - {entry.user.name} (ID: {entry.user.id}, '
                    f'現在の労働時間: {entry.total_hours_display}, ランク: {entry.rank})'
                )
        else:
            self.stdout.write(f'{target_year}年{target_month}月の参加者はいません')
    
    def _execute_recalculation(self, entries, target_year, target_month):
        """実際の再計算処理を実行"""
        if not entries:
            self.stdout.write(f'{target_year}年{target_month}月の参加者はいません')
            logger.info(f'再計算処理完了: 対象なし ({target_year}年{target_month}月)')
            return
        
        self.stdout.write(f'再計算処理を実行中... (対象: {len(entries)}エントリ)')
        
        success_count = 0
        error_count = 0
        
        # 各エントリを完全再計算
        for entry in entries:
            try:
                service = LeaderboardService(entry.user)
                result_entry, response = service.recalculate_user_stats_from_scratch(
                    year=target_year,
                    month=target_month
                )
                
                if response and response.get('success'):
                    success_count += 1
                    self.stdout.write(
                        f'  ✓ {entry.user.name}: {result_entry.total_hours_display} '
                        f'(前回: {entry.total_hours_display})'
                    )
                else:
                    error_count += 1
                    error_msg = response.get('error', '不明なエラー') if response else '不明なエラー'
                    self.stdout.write(
                        self.style.ERROR(f'  ✗ {entry.user.name}: {error_msg}')
                    )
                    logger.error(f'ユーザー {entry.user.name} の再計算失敗: {error_msg}')
                    
            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(f'  ✗ {entry.user.name}: 処理エラー - {str(e)}')
                )
                logger.error(f'ユーザー {entry.user.name} の再計算エラー', exc_info=True)
        
        # ランキングを更新
        if success_count > 0:
            self.stdout.write('ランキングを更新中...')
            service = LeaderboardService()
            ranking_result = service.update_leaderboard(target_year, target_month)
            
            if ranking_result.get('success'):
                self.stdout.write('ランキング更新完了')
            else:
                self.stdout.write(
                    self.style.ERROR(f'ランキング更新エラー: {ranking_result.get("error", "不明なエラー")}')
                )
                logger.error(f'ランキング更新エラー: {ranking_result}')
        
        # 結果サマリー
        self.stdout.write(f'再計算処理完了: 成功 {success_count}件, エラー {error_count}件')
        
        if error_count == 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f'{target_year}年{target_month}月のランキングデータ完全再計算が正常に完了しました'
                )
            )
            logger.info(f'ランキングデータ完全再計算完了: {target_year}年{target_month}月, 成功{success_count}件')
        else:
            self.stdout.write(
                self.style.WARNING(
                    f'{target_year}年{target_month}月のランキングデータ完全再計算が完了しました（一部エラーあり）'
                )
            )
            logger.warning(
                f'ランキングデータ完全再計算完了（エラーあり）: {target_year}年{target_month}月, '
                f'成功{success_count}件, エラー{error_count}件'
            )