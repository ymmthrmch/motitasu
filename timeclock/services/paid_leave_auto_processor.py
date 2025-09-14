"""
有給休暇自動処理クラス

自動処理とシグナル連携を担当し、システムの中核的な制御を行う
"""

from datetime import date
from typing import List, Optional
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from zoneinfo import ZoneInfo
import logging

from ..models import PaidLeaveRecord
from .paid_leave_calculator import PaidLeaveCalculator, PaidLeaveJudgment
from .paid_leave_grant_processor import PaidLeaveGrantProcessor
from .paid_leave_balance_manager import PaidLeaveBalanceManager

User = get_user_model()
logger = logging.getLogger(__name__)


class PaidLeaveAutoProcessor:
    """自動処理とシグナル連携を担当"""
    
    def __init__(self):
        """自動処理クラスのコンストラクタ"""
        pass
    
    @transaction.atomic
    def process_daily_grants_and_expirations(self, target_date: date) -> List[PaidLeaveJudgment]:
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
            
        Raises:
            ValueError: target_dateがNoneまたは無効な型の場合
        """
        # 入力値検証
        if target_date is None:
            raise ValueError("target_dateがNoneです")
        if not isinstance(target_date, date):
            raise TypeError(f"target_dateはdate型である必要があります。実際の型: {type(target_date)}")
        
        logger.info(f"日次付与処理を開始: {target_date}")
        
        judgments = []
        
        # target_dateが付与日のユーザーを効率的に取得
        eligible_users = User.objects.filter(
            is_active=True,
            hire_date__isnull=False
        ).exclude(paid_leave_grant_schedule=[])
        
        processed_users = 0
        grant_success_count = 0
        
        for user in eligible_users:
            try:
                # 指定日が付与日かチェック
                if user.is_grant_date_today(target_date):
                    # 付与回数を特定
                    grant_count = self._calculate_grant_count_for_date(user, target_date)
                    if grant_count is None:
                        logger.warning(f"付与回数の特定に失敗: user={user.name}, date={target_date}")
                        continue
                    
                    # 付与判定を実行
                    calculator = PaidLeaveCalculator(user)
                    judgment = calculator.judge_grant_eligibility(grant_count)
                    
                    judgments.append(judgment)
                    
                    # 付与条件を満たす場合は付与処理を実行
                    if judgment.is_eligible:
                        processor = PaidLeaveGrantProcessor(user)
                        processor.execute_grant(judgment)
                        grant_success_count += 1
                        logger.info(f"付与成功: user={user.name}, days={judgment.grant_days}")
                    
                    processed_users += 1
                    
                    # 時効処理も同時実行
                    try:
                        processor = PaidLeaveGrantProcessor(user)
                        expired_records = processor.process_expiration(target_date)
                        if expired_records:
                            logger.info(f"時効処理完了: user={user.name}, expired_records={len(expired_records)}")
                    except Exception as e:
                        logger.error(f"時効処理エラー: user={user.name}, error={str(e)}")
                    
            except Exception as e:
                logger.error(f"ユーザー処理中にエラー: user={user.name}, error={str(e)}")
                # 個別ユーザーのエラーは全体処理を止めない
                continue
        
        logger.info(f"日次付与処理完了: 処理対象={processed_users}名, 付与成功={grant_success_count}名")
        return judgments
    
    def _calculate_grant_count_for_date(self, user: User, target_date: date) -> Optional[int]:
        """指定日に対応する付与回数を計算"""
        calculator = PaidLeaveCalculator(user)
        
        # 付与スケジュールから該当する回数を特定
        for grant_count in range(1, 21):  # 最大20回まで確認
            try:
                calculated_date = calculator.calculate_grant_date(grant_count)
                if calculated_date == target_date:
                    return grant_count
            except Exception:
                break
        
        return None
    
    def process_time_record_change(self, user: User, record_date: date, change_type: str) -> List[PaidLeaveJudgment]:
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
            
        Raises:
            ValueError: record_dateがNoneまたは無効な型の場合
            TypeError: record_dateがdate型でない場合
        """
        # 入力値検証
        if record_date is None:
            raise ValueError("record_dateがNoneです")
        if not isinstance(record_date, date):
            raise TypeError(f"record_dateはdate型である必要があります。実際の型: {type(record_date)}")
        
        logger.info(f"TimeRecord変更処理開始: user={user.name}, record_date={record_date}, change_type={change_type}")
        
        # 基本的な前提条件チェック
        if not user.hire_date or not user.paid_leave_grant_schedule:
            return []
        
        # 現在日で直近付与日を取得（JST）
        jst = ZoneInfo('Asia/Tokyo')
        today = timezone.now().astimezone(jst).date()
        latest_grant_date = user.get_latest_grant_date(today)
        
        if latest_grant_date is None:
            # まだ一度も付与されていない場合、再判定対象外
            return []
        
        # 再判定が必要かチェック
        calculator = PaidLeaveCalculator(user)
        if not calculator.should_rejudge(record_date, today):
            return []
        
        return self._execute_rejudgment(user, record_date)
    
    @transaction.atomic
    def _execute_rejudgment(self, user: User, modified_record_date: date) -> List[PaidLeaveJudgment]:
        """再判定を実行"""
        judgments = []
        
        try:
            calculator = PaidLeaveCalculator(user)
            processor = PaidLeaveGrantProcessor(user)
            
            # 影響を受ける付与回を特定
            affected_grant = calculator.find_affected_grants(modified_record_date)
            
            if affected_grant is not None:
                # 現在の状態で再判定
                grant_date = calculator.calculate_grant_date(affected_grant)
                judgment = calculator.judge_grant_eligibility(affected_grant)
                
                judgments.append(judgment)
                
                # 以前の付与を取り消し
                PaidLeaveRecord.objects.filter(grant_date=grant_date, user=user, record_type='grant').delete()
                
                # 新たに付与条件を満たす場合は再付与
                if judgment.is_eligible:
                    processor.execute_grant(judgment)
                    logger.info(f"再判定で再付与: user={user.name}, grant_count={affected_grant}, days={judgment.grant_days}")
                else:
                    logger.info(f"再判定で付与なし: user={user.name}, grant_count={affected_grant}")
            
        except Exception as e:
            logger.error(f"再判定処理エラー: user={user.name}, error={str(e)}")
            # ロールバックはtransaction.atomicが処理
            raise
        
        return judgments
    
    def process_paid_leave_record_change(self, user: User, record, change_type: str) -> None:
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
        logger.info(f"PaidLeaveRecord変更処理: user={user.name}, record_type={record.record_type if record else 'None'}, change_type={change_type}")
        
        try:
            # 残日数を再計算・更新
            balance_manager = PaidLeaveBalanceManager(user)
            new_balance = balance_manager.update_user_balance()
            
            logger.info(f"残日数更新完了: user={user.name}, new_balance={new_balance}")
            
        except Exception as e:
            logger.error(f"残日数更新エラー: user={user.name}, error={str(e)}")
            # シグナル処理なので例外を再発生させて処理を停止
            raise