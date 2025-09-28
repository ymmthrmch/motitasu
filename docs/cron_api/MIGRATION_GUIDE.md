# Cron Job → Google Apps Script移行ガイド

## 移行手順

### 1. Renderのcron設定を無効化

`render.yaml`ファイルのcron設定をコメントアウト:

```yaml
# 以下をコメントアウトまたは削除
# - type: cron
#   name: daily-paid-leave-grants
#   env: python
#   buildCommand: pip install -r requirements.txt
#   schedule: "0 15 * * *"  # 毎日午前0時（JST）に実行（UTC 15時）
#   startCommand: python manage.py process_daily_paid_leave_grants

# - type: cron
#   name: cleanup-expired-pins
#   env: python
#   buildCommand: pip install -r requirements.txt
#   schedule: "*/5 * * * *"  # 5分おきに実行
#   startCommand: python manage.py cleanup_expired_pins
```

### 2. Django環境変数を追加

Renderの環境変数に以下を追加:

```
CRON_API_SECRET=your-32-character-or-longer-secret-key-here
```

**秘密鍵生成例:**
```python
import secrets
print(secrets.token_urlsafe(32))
```

### 3. Google Apps Scriptプロジェクト作成

1. [Google Apps Script](https://script.google.com/)にアクセス
2. 新しいプロジェクトを作成
3. `GOOGLE_APPS_SCRIPT_INTEGRATION.md`のコードをコピー
4. `CONFIG`セクションを実際の値に更新

### 4. トリガー設定

Google Apps Scriptエディターで:
1. トリガーアイコン（時計マーク）をクリック
2. 各関数のトリガーを設定:
   - `processDailyPaidLeaveGrants`: 毎日午前0時
   - `cleanupExpiredPins`: 5分ごと
   - `healthCheck`: 1時間ごと

### 5. テスト実行

各関数を手動実行してテスト:
1. 実行ログを確認
2. Django側のログを確認
3. APIレスポンスが正常であることを確認

## 旧Managementコマンドとの対応

| 旧Managementコマンド | 新APIエンドポイント | 説明 |
|-------------------|-------------------|------|
| `process_daily_paid_leave_grants` | `/api/cron/paid-leave-grants/` | 日次有給付与・時効処理 |
| `cleanup_expired_pins` | `/api/cron/cleanup-pins/` | 期限切れピン留め削除 |
| - | `/api/cron/health-check/` | 新規追加：システム監視 |

## 機能比較

### 旧Cron Job（Render）
- ✅ 確実なスケジュール実行
- ❌ 実行ログの確認が困難
- ❌ エラー通知機能なし
- ❌ 柔軟な監視設定が困難

### 新Google Apps Script
- ✅ 実行ログの詳細確認
- ✅ カスタムエラー通知
- ✅ スプレッドシート連携
- ✅ 柔軟なスケジュール設定
- ⚠️ Google Apps Scriptの制限あり（実行時間6分、日次実行制限）

## 注意事項

1. **実行時間制限**: Google Apps Scriptは6分の実行時間制限があります
2. **日次制限**: 無料版では1日20時間の実行時間制限があります
3. **エラーハンドリング**: ネットワークエラーや一時的な障害に対する再試行ロジックが必要
4. **タイムゾーン**: Google Apps Scriptとサーバーのタイムゾーン設定を確認

## ロールバック手順

問題が発生した場合の復旧方法:

1. Google Apps Scriptのトリガーを無効化
2. `render.yaml`のcron設定のコメントアウトを解除
3. Renderへの再デプロイ
4. 旧システムの動作確認

## 移行チェックリスト

- [ ] Renderのcron設定を無効化
- [ ] Django環境変数`CRON_API_SECRET`を設定
- [ ] Google Apps Scriptプロジェクト作成
- [ ] スクリプトコードを実装
- [ ] トリガー設定完了
- [ ] テスト実行成功
- [ ] 本番環境での動作確認
- [ ] 監視・アラート設定
- [ ] 旧Managementコマンドの削除（オプション）