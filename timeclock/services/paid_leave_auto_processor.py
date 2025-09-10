"""
有給休暇自動処理クラス
"""

from datetime import date
from typing import List
from django.contrib.auth import get_user_model

from .paid_leave_calculator import PaidLeaveCalculator, PaidLeaveJudgment
from .paid_leave_balance_manager import PaidLeaveBalanceManager
from .paid_leave_grant_processor import PaidLeaveGrantProcessor

User = get_user_model()


class PaidLeaveAutoProcessor:
    """自動処理とシグナル連携を担当"""
    
    def __init__(self):
        """自動処理クラスのコンストラクタ"""
        pass
    
    def process_daily_grants(self, target_date: date) -> List[PaidLeaveJudgment]:
        """
        指定日の全ユーザー付与処理
        
        Args:
            target_date: 処理対象日
            
        Returns:
            list[PaidLeaveJudgment]: 全ユーザーの判定結果
            
        Rules:
            - 全ユーザーのpaid_leave_grant_scheduleフィールドを参照
            - target_dateが付与日に含まれるユーザーのみを対象に付与処理を実行
            - cron処理から呼び出される
        """
        judgments = []
        
        # 全ユーザーを取得
        users = User.objects.filter(is_active=True)
        
        for user in users:
            try:
                # このユーザーが今日付与日かチェック
                if user.is_grant_date_today(target_date):
                    # 付与回数を特定
                    grant_count = self._determine_grant_count(user, target_date)
                    
                    if grant_count > 0:
                        # 付与処理実行
                        calculator = PaidLeaveCalculator(user)
                        processor = PaidLeaveGrantProcessor(user)
                        
                        # 判定実行
                        judgment = calculator.judge_grant_eligibility(grant_count, target_date)
                        judgments.append(judgment)
                        
                        # 付与処理実行
                        processor.execute_grant(judgment)
                        
            except Exception as e:
                # エラーログを記録（実装時に適切なロギングを追加）
                print(f"ユーザー {user.id} の付与処理でエラー: {e}")
                continue
        
        return judgments
    
    def process_time_record_change(self, user, record_date: date, change_type: str) -> List[PaidLeaveJudgment]:
        """
        TimeRecord変更に伴う自動再判定処理
        
        Args:
            user: 対象ユーザー
            record_date: 変更されたレコードの日付
            change_type: 変更タイプ ('create', 'update', 'delete')
            
        Returns:
            list[PaidLeaveJudgment]: 再判定結果のリスト
            
        Rules:
            - 変化があったTimeRecordのtimestampの日付がユーザーの直近の付与日以前の場合のみ処理
            - paid_leave_grant_scheduleフィールドから直近付与日を取得して判定
            - 再判定要否を判断し、影響を受ける付与回の再判定を実行
            - シグナルから呼び出される
        """
        judgments = []
        
        try:
            calculator = PaidLeaveCalculator(user)
            processor = PaidLeaveGrantProcessor(user)
            
            # 再判定が必要かチェック
            if not calculator.should_rejudge(record_date, date.today()):
                return judgments
            
            # 影響を受ける付与回を特定
            affected_grants = calculator.find_affected_grants(record_date)
            
            for grant_count in affected_grants:
                try:
                    # 該当する付与日を計算
                    grant_date = calculator.calculate_grant_date(grant_count)
                    
                    # 既に付与済みかチェック
                    from timeclock.models import PaidLeaveRecord
                    existing_grant = PaidLeaveRecord.objects.filter(
                        user=user,
                        record_type='grant',
                        grant_date=grant_date
                    ).first()
                    
                    if existing_grant:
                        # 再判定実行
                        new_judgment = calculator.judge_grant_eligibility(grant_count, grant_date)
                        judgments.append(new_judgment)
                        
                        # 既存の付与が適格だったが新判定で不適格になった場合
                        if existing_grant.days > 0 and not new_judgment.is_eligible:
                            # 取消処理実行
                            processor.execute_cancellation(
                                grant_count, date.today(), "再判定による取消"
                            )
                        
                        # 既存の付与が不適格だったが新判定で適格になった場合
                        elif existing_grant.days == 0 and new_judgment.is_eligible:
                            # 新たに付与処理実行
                            processor.execute_grant(new_judgment)
                        
                        # 付与日数に変更がある場合
                        elif existing_grant.days != new_judgment.grant_days and new_judgment.is_eligible:
                            # いったん取消してから新たに付与
                            processor.execute_cancellation(
                                grant_count, date.today(), "再判定による調整"
                            )
                            processor.execute_grant(new_judgment)
                
                except Exception as e:
                    print(f"付与回 {grant_count} の再判定でエラー: {e}")
                    continue
        
        except Exception as e:
            print(f"ユーザー {user.id} の再判定処理でエラー: {e}")
        
        return judgments
    
    def process_paid_leave_record_change(self, user, record, change_type: str) -> None:
        """
        PaidLeaveRecord変更に伴う残日数更新処理
        
        Args:
            user: 対象ユーザー
            record: 変更されたPaidLeaveRecord
            change_type: 変更タイプ ('create', 'update', 'delete')
            
        Rules:
            - 有給使用・付与・取消記録の変更を検知
            - 残日数の再計算と更新を実行
            - シグナルから呼び出される
        """
        try:
            balance_manager = PaidLeaveBalanceManager(user)
            balance_manager.update_user_balance()
        
        except Exception as e:
            print(f"ユーザー {user.id} の残日数更新でエラー: {e}")
    
    def _determine_grant_count(self, user, target_date: date) -> int:
        """
        指定日での付与回数を特定
        
        Args:
            user: 対象ユーザー
            target_date: 対象日
            
        Returns:
            int: 付与回数（該当しない場合は0）
        """
        calculator = PaidLeaveCalculator(user)
        
        # 最大20回まで確認
        for grant_count in range(1, 21):
            try:
                grant_date = calculator.calculate_grant_date(grant_count)
                if grant_date == target_date:
                    return grant_count
            except ValueError:
                # 計算エラーの場合は終了
                break
        
        return 0