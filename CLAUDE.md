# Claude設定

## 基本設定
- 応答言語: 日本語
- コーディングスタイル: Pythonic、DRY原則を重視
- コメント: 日本語で記述

## プロジェクト固有の設定

### コーディング規約
- PEP 8準拠
- 関数・変数名: snake_case
- クラス名: PascalCase
- 日本語コメントは簡潔に
- テストファイル名: test_*.py
- タイムゾーン: Asia/Tokyo

## ユーザー固有の設定

### 対話スタイル
- `[命令]`:基本的な指示が書いてあります
- `[コンテクスト]`:参照するファイルやディレクトリのパス、文章が書かれています

### 開発環境
- OS: macOS
- Python: python3コマンドを使用
- エディタ: VS Code連携

## 有給休暇計算ロジックの仕様
必ず`./docs/paid_leave/PAID_LEAVE_RULES.md`を参照すること。

## 禁止事項

### 🚨 **絶対に編集禁止のディレクトリ・ファイル** 🚨
以下のディレクトリ内のファイルは**読み込みと実行のみ**許可。**編集は絶対に行わないこと**：

1. **`/Users/yamamotoharumichi/Programming/PythonApps/Motitasu/motitasu/timeclock/tests`**
   - すべてのテストファイル（`test_*.py`）
   - 読み込み：✅ 許可
   - 実行（`manage.py test`等）：✅ 許可
   - 編集：❌ **絶対禁止**

2. **`/Users/yamamotoharumichi/Programming/PythonApps/Motitasu/motitasu/docs/paid_leave`**
   - すべての仕様書・ドキュメント（`.md`ファイル）
   - 読み込み：✅ 許可
   - 編集：❌ **絶対禁止**

### 対応方法
- **疑問点がある場合**：ユーザーに質問して確認
- **修正が必要な場合**：
  1. 問題箇所を具体的に指摘
  2. 修正案を提示
  3. ユーザーに編集を依頼
  4. ユーザーが編集完了後に作業継続

### その他の禁止事項
- `./docs`内のその他のファイルも読み取りのみ

## Render デプロイ後作業チェックリスト

### 🚀 有給休暇日次処理（Cron）の本番環境設定

#### **前提条件**
- ✅ Management Command実装済み: `process_daily_paid_leave_grants.py`
- ✅ render.yamlのcron設定完了: 毎日UTC 15時（JST 0時）実行

#### **デプロイ後の必須作業**

##### **1. 環境変数設定（Render Web UI）**
```
DATABASE_URL = [PostgreSQL接続文字列]
SECRET_KEY = [Django秘密鍵]
DEBUG = False
ALLOWED_HOSTS = [デプロイ先ドメイン]
TZ = Asia/Tokyo
DJANGO_SETTINGS_MODULE = motitasu.settings
```

##### **2. 動作テスト実行**
```bash
# DRY-RUNモードでテスト
render run python manage.py process_daily_paid_leave_grants --dry-run

# 特定日付でのテスト
render run python manage.py process_daily_paid_leave_grants --dry-run --date 2023-07-01
```

##### **3. ログ確認**
```bash
# Cronジョブのログ確認
render logs --service daily-paid-leave-grants

# Webアプリのログも確認
render logs --service motitasu
```

##### **4. タイムゾーン動作確認**
- 日本時間午前0時に実行されるかテスト
- 必要に応じてcronスケジュール調整

#### **トラブルシューティング**

##### **エラーが発生した場合**
1. ログでエラー内容確認
2. データベース接続確認
3. 環境変数設定再確認
4. DRY-RUNモードで個別テスト

##### **スケジュール調整が必要な場合**
```yaml
# render.yamlのschedule修正例
schedule: "0 15 * * *"  # UTC 15時 = JST 0時
schedule: "0 16 * * *"  # UTC 16時 = JST 1時（サマータイム対応）
```

#### **運用開始後の監視項目**
- 日次実行の成功/失敗
- 処理時間の監視
- エラーログの監視
- 付与結果の妥当性確認

### 設定完了確認
- [ ] 環境変数設定完了
- [ ] DRY-RUNテスト成功
- [ ] ログ出力確認
- [ ] タイムゾーン動作確認
- [ ] 本番実行テスト完了