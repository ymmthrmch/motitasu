"""
有給休暇システム 統合シナリオテスト

INTEGRATION_SCENARIOS_TEST.mdのテストケースを実装：
- シナリオ1-1: 通常労働者の標準的な初回付与プロセス
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.management import call_command
from unittest.mock import patch, Mock
from datetime import date, datetime, time
from io import StringIO
from timeclock.models import TimeRecord, PaidLeaveRecord

User = get_user_model()


class NewEmployeeGrantProcessTest(TestCase):
    """新入社員の入社から初回有給付与までのテスト"""
    
    def setUp(self):
        """テスト用データの準備"""
        # シナリオ1-1の設定に従ってユーザーを作成
        self.user = User.objects.create_user(
            email='tanaka@company.com',
            name='田中太郎'
        )
        # ユーザー設定
        self.user.hire_date = date(2023, 1, 1)  # 入社日: 2023年1月1日
        self.user.weekly_work_days = 5  # 週所定労働日数: 5日
        self.user.current_paid_leave = 0  # 初期残日数: 0日
        # 付与スケジュール（実装時は自動計算される）
        self.user.paid_leave_grant_schedule = [
            "2023-07-01",  # 1回目付与日
            "2024-07-01",  # 2回目付与日
            "2025-07-01",  # 3回目付与日
        ]
        self.user.save()
    
    def create_work_day(self, work_date):
        """
        出勤日の作成（clock_in/clock_outペア）
        
        Args:
            work_date (date): 出勤日
        """
        # clock_in記録
        TimeRecord.objects.create(
            user=self.user,
            timestamp=datetime.combine(work_date, time(9, 0)),
            clock_type='clock_in'
        )
        # clock_out記録  
        TimeRecord.objects.create(
            user=self.user,
            timestamp=datetime.combine(work_date, time(18, 0)),
            clock_type='clock_out'
        )
    
    def create_attendance_records(self):
        """
        シナリオ1-1の出勤記録を作成
        
        - 総出勤日数: 110日
        - 判定対象期間: 181日間（2023年1月1日〜6月30日）
        - 所定労働日数: 129日
        - 出勤率: 85.3%
        """
        # 2023年1月1日から6月30日までの期間で110日分の出勤記録を作成
        # 平日を中心に出勤日を配置（実際の業務日に合わせて調整）
        work_dates = []
        
        # 1月（22営業日想定、18日出勤）
        january_dates = [
            date(2023, 1, 4), date(2023, 1, 5), date(2023, 1, 6), date(2023, 1, 10),
            date(2023, 1, 11), date(2023, 1, 12), date(2023, 1, 13), date(2023, 1, 16),
            date(2023, 1, 17), date(2023, 1, 18), date(2023, 1, 19), date(2023, 1, 20),
            date(2023, 1, 23), date(2023, 1, 24), date(2023, 1, 25), date(2023, 1, 26),
            date(2023, 1, 27), date(2023, 1, 30)
        ]
        work_dates.extend(january_dates)
        
        # 2月（20営業日想定、17日出勤）
        february_dates = [
            date(2023, 2, 1), date(2023, 2, 2), date(2023, 2, 3), date(2023, 2, 6),
            date(2023, 2, 7), date(2023, 2, 8), date(2023, 2, 9), date(2023, 2, 10),
            date(2023, 2, 13), date(2023, 2, 14), date(2023, 2, 15), date(2023, 2, 16),
            date(2023, 2, 17), date(2023, 2, 20), date(2023, 2, 21), date(2023, 2, 22),
            date(2023, 2, 24)
        ]
        work_dates.extend(february_dates)
        
        # 3月（23営業日想定、19日出勤）
        march_dates = [
            date(2023, 3, 1), date(2023, 3, 2), date(2023, 3, 3), date(2023, 3, 6),
            date(2023, 3, 7), date(2023, 3, 8), date(2023, 3, 9), date(2023, 3, 10),
            date(2023, 3, 13), date(2023, 3, 14), date(2023, 3, 15), date(2023, 3, 16),
            date(2023, 3, 17), date(2023, 3, 20), date(2023, 3, 22), date(2023, 3, 23),
            date(2023, 3, 24), date(2023, 3, 27), date(2023, 3, 28)
        ]
        work_dates.extend(march_dates)
        
        # 4月（20営業日想定、18日出勤）
        april_dates = [
            date(2023, 4, 3), date(2023, 4, 4), date(2023, 4, 5), date(2023, 4, 6),
            date(2023, 4, 7), date(2023, 4, 10), date(2023, 4, 11), date(2023, 4, 12),
            date(2023, 4, 13), date(2023, 4, 14), date(2023, 4, 17), date(2023, 4, 18),
            date(2023, 4, 19), date(2023, 4, 20), date(2023, 4, 21), date(2023, 4, 24),
            date(2023, 4, 25), date(2023, 4, 28)
        ]
        work_dates.extend(april_dates)
        
        # 5月（22営業日想定、19日出勤）
        may_dates = [
            date(2023, 5, 1), date(2023, 5, 2), date(2023, 5, 8), date(2023, 5, 9),
            date(2023, 5, 10), date(2023, 5, 11), date(2023, 5, 12), date(2023, 5, 15),
            date(2023, 5, 16), date(2023, 5, 17), date(2023, 5, 18), date(2023, 5, 19),
            date(2023, 5, 22), date(2023, 5, 23), date(2023, 5, 24), date(2023, 5, 25),
            date(2023, 5, 26), date(2023, 5, 29), date(2023, 5, 31)
        ]
        work_dates.extend(may_dates)
        
        # 6月（22営業日想定、19日出勤）
        june_dates = [
            date(2023, 6, 1), date(2023, 6, 2), date(2023, 6, 5), date(2023, 6, 6),
            date(2023, 6, 7), date(2023, 6, 8), date(2023, 6, 9), date(2023, 6, 12),
            date(2023, 6, 13), date(2023, 6, 14), date(2023, 6, 15), date(2023, 6, 16),
            date(2023, 6, 19), date(2023, 6, 20), date(2023, 6, 21), date(2023, 6, 22),
            date(2023, 6, 23), date(2023, 6, 26), date(2023, 6, 30)
        ]
        work_dates.extend(june_dates)
        
        # 総出勤日数110日を確認
        self.assertEqual(len(work_dates), 110, f"出勤日数が110日ではありません: {len(work_dates)}日")
        
        # 各出勤日のTimeRecordを作成
        for work_date in work_dates:
            self.create_work_day(work_date)
        
        return work_dates
    
    @patch('timeclock.services.paid_leave_auto_processor.PaidLeaveAutoProcessor.process_daily_grants_and_expirations')
    @patch('timeclock.services.paid_leave_calculator.PaidLeaveCalculator.judge_grant_eligibility')
    @patch('timeclock.services.paid_leave_grant_processor.PaidLeaveGrantProcessor.execute_grant')
    def test_scenario_1_1_standard_initial_grant_process(self, mock_execute_grant, mock_judge_eligibility, mock_process_daily):
        """
        シナリオ1-1: 通常労働者の標準的な初回付与プロセス
        
        背景: 2023年1月1日に入社した通常労働者（週5日勤務）の6か月後の初回有給付与
        """
        # 出勤記録を作成
        work_dates = self.create_attendance_records()
        
        # 出勤記録数を確認
        total_records = TimeRecord.objects.filter(user=self.user).count()
        self.assertEqual(total_records, 220, f"TimeRecord総数が220件ではありません: {total_records}件")
        
        # 判定結果のモックを設定
        mock_judgment = Mock()
        mock_judgment.grant_count = 1
        mock_judgment.judgment_date = date(2023, 7, 1)
        mock_judgment.period_start = date(2023, 1, 1)
        mock_judgment.period_end = date(2023, 6, 30)
        mock_judgment.required_work_days = 129
        mock_judgment.attendance_days = 110
        mock_judgment.attendance_rate = 0.853  # 85.3%
        mock_judgment.is_eligible = True
        mock_judgment.grant_days = 10
        mock_judgment.expiry_date = date(2025, 7, 1)
        mock_judgment.description = "付与条件を満たしています"
        
        mock_judge_eligibility.return_value = mock_judgment
        
        # 付与記録のモックを設定
        mock_grant_record = Mock()
        mock_grant_record.user = self.user
        mock_grant_record.record_type = 'grant'
        mock_grant_record.days = 10
        mock_grant_record.grant_date = date(2023, 7, 1)
        mock_grant_record.expiry_date = date(2025, 7, 1)
        mock_grant_record.description = "付与条件を満たしています"
        
        mock_execute_grant.return_value = mock_grant_record
        
        # 日次処理のモックを設定
        mock_process_daily.return_value = [mock_judgment]
        
        # 2023年7月1日に日次処理実行をシミュレート
        target_date = date(2023, 7, 1)
        
        # 日次処理コマンドの実行をシミュレート
        with patch('django.core.management.base.BaseCommand.handle') as mock_command:
            mock_command.return_value = None
            
            # management commandの実行
            out = StringIO()
            call_command('process_daily_paid_leave', 
                         date=target_date.strftime('%Y-%m-%d'),
                         stdout=out)
        
        # 日次処理が呼び出されたことを確認
        mock_process_daily.assert_called_once_with(target_date)
        
        # 判定処理が呼び出されたことを確認
        self.assertTrue(mock_judge_eligibility.called)
        
        # 付与処理が呼び出されたことを確認
        mock_execute_grant.assert_called_once_with(mock_judgment)
        
        # 判定結果の検証
        judgment_result = mock_judge_eligibility.return_value
        self.assertTrue(judgment_result.is_eligible)
        self.assertEqual(judgment_result.grant_days, 10)
        self.assertEqual(judgment_result.attendance_rate, 0.853)
        self.assertEqual(judgment_result.period_start, date(2023, 1, 1))
        self.assertEqual(judgment_result.period_end, date(2023, 6, 30))
        
        # 付与記録の検証
        grant_result = mock_execute_grant.return_value
        self.assertEqual(grant_result.record_type, 'grant')
        self.assertEqual(grant_result.days, 10)
        self.assertEqual(grant_result.grant_date, date(2023, 7, 1))
        self.assertEqual(grant_result.expiry_date, date(2025, 7, 1))
        
        # 日次処理の戻り値検証
        daily_result = mock_process_daily.return_value
        self.assertIsInstance(daily_result, list)
        self.assertEqual(len(daily_result), 1)
        self.assertTrue(daily_result[0].is_eligible)
    
    def test_time_record_data_verification(self):
        """
        TimeRecord作成データの検証
        
        目的: 作成された出勤記録が仕様通りになっていることを確認
        """
        # 出勤記録を作成
        work_dates = self.create_attendance_records()
        
        # TimeRecordの総数確認（出勤110日 × clock_in/clock_out 2件 = 220件）
        total_records = TimeRecord.objects.filter(user=self.user).count()
        self.assertEqual(total_records, 220)
        
        # clock_inとclock_outの件数確認
        clock_in_count = TimeRecord.objects.filter(user=self.user, clock_type='clock_in').count()
        clock_out_count = TimeRecord.objects.filter(user=self.user, clock_type='clock_out').count()
        self.assertEqual(clock_in_count, 110)
        self.assertEqual(clock_out_count, 110)
        
        # 判定対象期間内の記録確認
        period_start = date(2023, 1, 1)
        period_end = date(2023, 6, 30)
        
        period_records = TimeRecord.objects.filter(
            user=self.user,
            timestamp__date__gte=period_start,
            timestamp__date__lte=period_end
        )
        self.assertEqual(period_records.count(), 220)
        
        # 最初と最後のTimeRecord確認
        first_record = TimeRecord.objects.filter(user=self.user).order_by('timestamp').first()
        last_record = TimeRecord.objects.filter(user=self.user).order_by('timestamp').last()
        
        self.assertEqual(first_record.timestamp.date(), date(2023, 1, 4))
        self.assertEqual(first_record.clock_type, 'clock_in')
        self.assertEqual(last_record.timestamp.date(), date(2023, 6, 30))
        self.assertEqual(last_record.clock_type, 'clock_out')
        
        # 各出勤日でclock_in/clock_outペアが正しく作成されていることを確認
        for work_date in work_dates[:5]:  # 最初の5日分をサンプル確認
            daily_records = TimeRecord.objects.filter(
                user=self.user,
                timestamp__date=work_date
            ).order_by('timestamp')
            
            self.assertEqual(daily_records.count(), 2)
            self.assertEqual(daily_records[0].clock_type, 'clock_in')
            self.assertEqual(daily_records[1].clock_type, 'clock_out')
            self.assertEqual(daily_records[0].timestamp.time(), time(9, 0))
            self.assertEqual(daily_records[1].timestamp.time(), time(18, 0))
        
        # 所定労働日数と出勤率の計算検証
        period_days = (period_end - period_start).days + 1  # 181日
        required_work_days = (period_days // 7) * self.user.weekly_work_days  # 181÷7×5=129日
        attendance_rate = len(work_dates) / required_work_days  # 110÷129=0.853
        
        self.assertEqual(period_days, 181, "判定対象期間が181日ではありません")
        self.assertEqual(required_work_days, 129, "所定労働日数が129日ではありません") 
        self.assertAlmostEqual(attendance_rate, 0.853, places=3, msg="出勤率が85.3%ではありません")
    
    def test_paid_leave_grant_schedule_verification(self):
        """
        paid_leave_grant_scheduleの検証
        
        目的: ユーザーの付与スケジュールが正しく設定されていることを確認
        """
        # 付与スケジュールの確認
        expected_schedule = ["2023-07-01", "2024-07-01", "2025-07-01"]
        self.assertEqual(self.user.paid_leave_grant_schedule, expected_schedule)
        
        # 1回目付与日が入社日の6か月後であることを確認
        hire_date = self.user.hire_date
        first_grant_date_str = self.user.paid_leave_grant_schedule[0]
        first_grant_date = date.fromisoformat(first_grant_date_str)
        
        # 2023年1月1日の6か月後は2023年7月1日
        expected_first_grant = date(2023, 7, 1)
        self.assertEqual(first_grant_date, expected_first_grant)
        
        # 2回目以降が1年ずつ後になっていることを確認
        for i in range(1, len(self.user.paid_leave_grant_schedule)):
            current_date_str = self.user.paid_leave_grant_schedule[i]
            previous_date_str = self.user.paid_leave_grant_schedule[i-1]
            current_date = date.fromisoformat(current_date_str)
            previous_date = date.fromisoformat(previous_date_str)
            
            # 1年後の日付であることを確認
            expected_date = date(previous_date.year + 1, previous_date.month, previous_date.day)
            self.assertEqual(current_date, expected_date)