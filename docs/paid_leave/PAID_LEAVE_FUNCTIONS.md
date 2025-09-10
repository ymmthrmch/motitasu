# 有給休暇付与システム - 関数設計

## 概要

有給休暇付与システムで実装すべき関数とクラスの設計を定義します。テストコードではこれらの関数を呼び出してテストを行います。

### 1. 実現すること
- その日が付与日のユーザーの有給休暇付与の判定と付与を行う
- 次の付与日がいつで、それまでにあと何日出勤すれば有給休暇が何日付与されるのかをユーザーに知らせる
- 有給休暇の付与、使用、時効、削除を管理し、計算した残日数をユーザーモデルに保存する
- 有給休暇の付与、取消があった際にユーザーモデルの残日数を更新、修正する
- 通常ではない手動での打刻記録の保存、変更、削除があった際に、影響のある付与日の有給休暇付与判定と付与をやり直す

### 2. 具体的な実現方法
- ./timeclock/services:有給休暇付与判定や付与を実現するためのメソッドを定義
- cron処理:有給休暇付与の判定と付与を実現するためのコマンドを./timeclock/management/commandsに定義し、デプロイ先であるRenderのcron処理を用いて1日1回の付与判定と付与を自動的に実行
- ./timeclock/signals
    - 有給休暇の付与、変更、時効、削除があった際に自動で発火し、ユーザーモデルの残日数を更新、修正する
    - 通常ではない手動での打刻記録の保存、変更、削除があった際に自動で発火し、影響のある付与日の判定、付与をやり直す（付与した有給を取り消す際にはPaidLeaveRecordのdaysを変更することで実現する）

---

## アーキテクチャ設計

### コア機能の分離と責任分担

システム全体を以下の4つのコア機能に分離し、それぞれに特化したクラスを設計します：

1. **PaidLeaveCalculator**: 純粋な計算処理（付与日、出勤率、判定）
2. **PaidLeaveBalanceManager**: 残日数管理と更新処理
3. **PaidLeaveGrantProcessor**: 付与・取消の実行処理
4. **PaidLeaveAutoProcessor**: 自動処理とシグナル連携

### データフローとプロセス設計

```
[TimeRecord/PaidLeaveRecord変更] 
    ↓ (Django Signal)
[PaidLeaveAutoProcessor] 
    ↓ (再判定判断)
[PaidLeaveCalculator] (計算処理)
    ↓ (判定結果)
[PaidLeaveGrantProcessor] (付与実行/取消処理)
    ↓ (残日数影響)
[PaidLeaveBalanceManager] (残日数更新)
    ↓ 
[User.current_paid_leave更新]
```

---

## クラス設計

### PaidLeaveCalculator クラス

有給休暇に関する純粋な計算処理を担当するクラス

#### コンストラクタ
```python
def __init__(self, user):
    """
    Args:
        user: Userモデルのインスタンス
    """
```

#### 付与日計算メソッド

```python
def calculate_grant_date(self, grant_count: int) -> date:
    """
    指定回数目の付与日を計算
    
    Args:
        grant_count: 付与回数（1回目、2回目...）
        
    Returns:
        date: 付与日
        
    Rules:
        - 1回目：入社日の6か月後
        - 2回目以降：1回目付与日のn年後
        - 月単位計算、存在しない日は月末に調整
    """
```

```python
def calculate_judgment_period(self, grant_count: int) -> tuple[date, date]:
    """
    判定対象期間を計算
    
    Args:
        grant_count: 付与回数
        
    Returns:
        tuple[date, date]: (開始日, 終了日)
        
    Rules:
        - 1回目：入社日 〜 付与日前日
        - 2回目以降：前回付与日 〜 今回付与日前日
    """
```

```python
def get_next_grant_info(self, reference_date: date = None) -> 'NextGrantInfo':
    """
    次回付与情報を取得（ユーザー向け情報表示用）
    
    Args:
        reference_date: 基準日（Noneの場合は今日）
        
    Returns:
        NextGrantInfo: 次回付与の詳細情報
        
    Rules:
        - 次回付与日、必要出勤日数、予定付与日数を計算
        - 現在の出勤状況も含める
    """
```

#### 出勤率計算メソッド

```python
def calculate_required_work_days(self, start_date: date, end_date: date) -> int:
    """
    所定労働日数を計算
    
    Args:
        start_date: 期間開始日
        end_date: 期間終了日
        
    Returns:
        int: 所定労働日数（小数点以下切り捨て）
        
    Rules:
        - 計算式：(期間日数 ÷ 7) × 週所定労働日数
        - 小数点以下切り捨て
    """
```

```python
def calculate_attendance(self, start_date: date, end_date: date) -> tuple[int, float]:
    """
    出勤日数を計算（実出勤 + 有給取得）
    出勤率を計算（出勤日数/所定労働日数）

    Args:
        start_date: 期間開始日
        end_date: 期間終了日
          
    Returns:
        tuple[int, float]: (出勤日数, 出勤率（0.0〜1.0）)
          
    Rules:
        - 実出勤日数 + 有給休暇取得日数
        - 出勤率 = 出勤日数 ÷ 所定労働日数

    Raises:
        ValueError: start_dateよりend_dateが過去の場合
    """
```

#### 付与判定メソッド

```python
def determine_grant_days(self, grant_count: int, weekly_work_days: int) -> int:
    """
    付与日数を決定
    
    Args:
        grant_count: 付与回数
        weekly_work_days: 週所定労働日数
        
    Returns:
        int: 付与日数
        
    Rules:
        - 勤続年数と週所定労働日数から付与日数テーブルを参照
        - 週5日以上は通常労働者テーブル
        - 週4日以下は比例付与テーブル
    """
```

```python
def judge_grant_eligibility(self, grant_count: int, judgment_date: date) -> 'PaidLeaveJudgment':
    """
    付与可否を総合判定
    
    Args:
        grant_count: 付与回数
        judgment_date: 判定日
        
    Returns:
        PaidLeaveJudgment: 判定結果
        
    Rules:
        - 在籍状況チェック
        - 出勤率80%以上チェック
        - その他必要条件のチェック
    """
```

#### 再判定関連メソッド

```python
def should_rejudge(self, modified_record_date: date, modification_date: date) -> bool:
    """
    再判定が必要かを判断
    
    Args:
        modified_record_date: 修正された記録の日付
        modification_date: 修正が行われた日
        
    Returns:
        bool: 再判定が必要な場合True
        
    Rules:
        - 修正された記録の日付が直近付与日より過去の場合に再判定
        - ルール文書の再判定例に準拠
    """
```

```python
def find_affected_grants(self, modified_record_date: date) -> list[int]:
    """
    修正により影響を受ける付与回を特定
    
    Args:
        modified_record_date: 修正された記録の日付
        
    Returns:
        list[int]: 影響を受ける付与回のリスト
        
    Rules:
        - 修正された記録の日付が判定対象期間に含まれる付与回を特定
    """
```

#### 有効期限関連メソッド

```python
def calculate_expiry_date(self, grant_date: date) -> date:
    """
    有効期限を計算
    
    Args:
        grant_date: 付与日
        
    Returns:
        date: 有効期限（付与日から2年後）
        
    Rules:
        - 付与日から2年後の同日
        - 存在しない日は月末に調整
    """
```

---

### PaidLeaveBalanceManager クラス

有給残日数の管理と更新処理を担当

```python
def __init__(self, user):
    """
    Args:
        user: Userモデルのインスタンス
    """
```

```python
def get_current_balance(self) -> int:
    """
    現在の有給残日数を計算
    
    Returns:
        int: 現在の有給残日数
        
    Rules:
        - データベースから最新の有給残日数を計算
        - 付与記録・使用記録・時効記録・取消記録を考慮
    """
```

```python
def get_detailed_balance_info(self) -> 'DetailedBalanceInfo':
    """
    詳細な残日数情報を取得
    
    Returns:
        DetailedBalanceInfo: 付与年度別の残日数詳細
        
    Rules:
        - 各付与年度の残日数を計算
        - 時効が近い順に並べる
    """
```

```python
def update_user_balance(self) -> int:
    """
    ユーザーモデルの残日数を最新値に更新
    
    Returns:
        int: 更新後の残日数
        
    Rules:
        - 計算した残日数をuser.current_paid_leaveに保存
    """
```

```python
def calculate_partial_cancellation(self, target_cancel_days: int, target_date: date) -> tuple[int, int]:
    """
    部分取消の計算（残日数がマイナスにならない範囲で取消）
    cancellationのPaidLeaveRecordを作成
    
    Args:
        target_cancel_days: 取消したい日数
        target_date: 取り消しを行う有給のgrant_date
        
    Returns:
        tuple[int, int]: (実際の取消日数, 取消後の残日数)
        
    Rules:
        - 残日数がマイナスにならない範囲で取消
        - actual_cancellation = min(target_cancel_days, current_balance)
        - remaining_after = current_balance - actual_cancellation
        - cancellationのPaidLeaveRecordを作成
    """
```

---

### PaidLeaveGrantProcessor クラス

付与・取消の実行処理を担当

```python
def __init__(self, user):
    """
    Args:
        user: Userモデルのインスタンス
    """
```

```python
def execute_grant(self, judgment: 'PaidLeaveJudgment') -> 'PaidLeaveRecord':
    """
    付与処理を実行
    
    Args:
        judgment: 付与判定結果
        
    Returns:
        PaidLeaveRecord: 作成された付与記録
        
    Rules:
        - 判定結果に基づいてPaidLeaveRecordを作成
        - 残日数の更新も実行
    """
```

```python
def execute_cancellation(self, grant_count: int, cancellation_date: date, reason: str) -> 'CancellationResult':
    """
    付与取消処理を実行（部分取消対応）
    
    Args:
        grant_count: 取消対象の付与回数
        cancellation_date: 取消日
        reason: 取消理由
        
    Returns:
        CancellationResult: 取消処理結果
        
    Rules:
        - 指定回の付与を部分取消で処理
        - 残日数がマイナスにならない範囲でのみ取消
        - 取消記録をPaidLeaveRecordに作成
    """
```

```python
def process_expiration(self, target_date: date) -> list['PaidLeaveRecord']:
    """
    時効消滅処理を実行
    
    Args:
        target_date: 処理対象日
        
    Returns:
        list[PaidLeaveRecord]: 消滅させた有給記録のリスト
        
    Rules:
        - target_date時点で期限切れの未使用有給を消滅
        - 時効記録をPaidLeaveRecordに作成
    """
```

---

### PaidLeaveAutoProcessor クラス

自動処理とシグナル連携を担当

```python
def __init__(self):
    """自動処理クラスのコンストラクタ"""
```

```python
def process_daily_grants(self, target_date: date) -> list['PaidLeaveJudgment']:
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
```

```python
def process_time_record_change(self, user, record_date: date, change_type: str) -> list['PaidLeaveJudgment']:
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
```

```python
def process_paid_leave_record_change(self, user, record: 'PaidLeaveRecord', change_type: str) -> None:
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
```

---

## データクラス設計

### PaidLeaveJudgment データクラス

```python
@dataclass
class PaidLeaveJudgment:
    """有給付与判定結果"""
    grant_count: int              # 付与回数
    judgment_date: date           # 判定日
    period_start: date            # 判定期間開始日
    period_end: date              # 判定期間終了日
    required_work_days: int       # 所定労働日数
    attendance_days: int          # 出勤日数
    attendance_rate: float        # 出勤率
    is_eligible: bool             # 付与可否
    grant_days: int               # 付与日数
    expiry_date: date            # 有効期限
    reason: str                   # 判定理由
```

### NextGrantInfo データクラス

```python
@dataclass
class NextGrantInfo:
    """次回付与情報（ユーザー向け表示用）"""
    next_grant_date: date         # 次回付与日
    days_until_grant: int         # 付与日まで残り日数
    current_attendance_days: int   # 現時点の出勤日数
    required_attendance_days: int  # 必要出勤日数（80%基準）
    remaining_attendance_needed: int # あと何日出勤が必要か
    expected_grant_days: int      # 予定付与日数
    current_attendance_rate: float # 現時点の出勤率
```

### DetailedBalanceInfo データクラス

```python
@dataclass
class DetailedBalanceInfo:
    """詳細残日数情報"""
    total_balance: int           # 合計残日数
    balance_by_grant_date: list['GrantDateBalance']  # 付与日別残日数
    upcoming_expirations: list['ExpirationInfo']    # 近い時効情報
```

```python
@dataclass
class GrantDateBalance:
    """付与日別残日数"""
    grant_date: date            # 付与日
    original_days: int          # 元の付与日数
    used_days: int              # 使用済み日数
    remaining_days: int         # 残り日数
    expiry_date: date          # 有効期限
    days_until_expiry: int     # 時効まで日数
```

```python
@dataclass
class CancellationResult:
    """取消処理結果"""
    grant_count: int            # 取消対象の付与回数
    target_cancel_days: int     # 当初の取消予定日数
    actual_cancelled_days: int  # 実際に取り消された日数
    remaining_balance: int      # 取消後の残日数
    was_partial: bool          # 部分取消だったか
    cancellation_date: date    # 取消日
    reason: str                # 取消理由
```

---

## Userモデル拡張設計

### 付与スケジュール関連メソッド

Userモデルに以下のメソッドを追加して、`paid_leave_grant_schedule`フィールドの操作を担当します。

```python
def get_latest_grant_date(self, reference_date: date = None) -> Optional[date]:
    """
    指定日時点での直近の付与日を取得
    
    Args:
        reference_date: 基準日（Noneの場合は今日）
        
    Returns:
        Optional[date]: 直近の付与日（まだ付与日がない場合はNone）
        
    Rules:
        - self.paid_leave_grant_scheduleから基準日以前の最新付与日を取得
        - シグナル処理での判定に使用
    """
```

```python
def is_grant_date_today(self, target_date: date) -> bool:
    """
    指定日がこのユーザーの付与日かを判定
    
    Args:
        target_date: 判定対象日
        
    Returns:
        bool: 付与日の場合True
        
    Rules:
        - self.paid_leave_grant_scheduleフィールドを参照
        - 日次処理での対象者判定に使用
    """
```

```python
def save(self, *args, **kwargs):
    """
    Userモデルのsaveメソッドをオーバーライド
    
    Rules:
        - hire_dateが変更された場合、paid_leave_grant_scheduleを自動更新
        - 入社日から全ての付与日を計算（1回目〜20回目程度）
        - super().save()を呼び出してデータベースに保存
    """
```

```python
def _calculate_grant_schedule(self) -> list[date]:
    """
    入社日に基づいて付与スケジュールを計算（内部メソッド）
    
    Returns:
        list[date]: 付与日のリスト
        
    Rules:
        - PaidLeaveCalculatorを使用して各回の付与日を計算
        - 1回目〜20回目程度の付与日を事前計算
    """
```

---

## シグナル設計

### TimeRecord変更時のシグナル

```python
@receiver(post_save, sender=TimeRecord)
@receiver(post_delete, sender=TimeRecord)
def handle_time_record_change(sender, instance, **kwargs):
    """
    TimeRecord変更時の自動再判定
    
    処理内容:
        1. 変更されたレコードの日付と対象ユーザーを特定
        2. PaidLeaveAutoProcessorを使用して再判定処理を実行
        3. シグナル無効化フラグをチェック（テスト時等）
    """
```

### PaidLeaveRecord変更時のシグナル

```python
@receiver(post_save, sender=PaidLeaveRecord)
@receiver(post_delete, sender=PaidLeaveRecord)
def handle_paid_leave_record_change(sender, instance, **kwargs):
    """
    PaidLeaveRecord変更時の残日数更新
    
    処理内容:
        1. 有給使用・付与・取消記録の変更を検知
        2. PaidLeaveAutoProcessorを使用して残日数更新処理を実行
        3. シグナル無効化フラグをチェック（テスト時等）
    """
```

---

## Management Command設計

### 日次付与処理コマンド

```python
class Command(BaseCommand):
    """日次有給付与処理コマンド（cron実行用）"""
    
    def add_arguments(self, parser):
        """コマンド引数の定義"""
        
    def handle(self, *args, **options):
        """
        実行内容:
            1. 本日の日付で全ユーザーの付与処理を実行
            2. 時効消滅処理も同時実行
            3. 処理結果をログ出力
        """
```

---

## テストサポート設計

```python
class SignalDisabler:
    """
    テスト時にシグナルを無効化するコンテキストマネージャー
    
    Usage:
        with SignalDisabler():
            # この中ではシグナルが動作しない
            TimeRecord.objects.create(...)
    """
```

---

## 実装時の注意事項

### エラーハンドリング
- 無効な日付データに対する適切な例外処理
- データベースアクセスエラーの処理
- 境界値（週0日勤務等）の適切な処理

### パフォーマンス考慮
- 大量ユーザーに対する効率的な処理
- データベースクエリの最適化
- 不要な重複計算の回避

### ログ出力
- 判定過程の詳細なログ出力
- エラー発生時のトレーサビリティ確保
- デバッグ用の中間値出力

この設計に基づいてテストコードを修正し、実際の実装を行います。