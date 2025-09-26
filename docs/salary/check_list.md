# Salary管理画面バックエンド接続チェックリスト

## 📋 チェック対象画面・機能一覧

### 🎯 **Phase 1: メイン管理画面（優先度: 高）**

- [ ] **1. ダッシュボード**
  - URL: `/salary/admin/dashboard/`
  - ビュー: `AdminDashboardView`
  - チェック項目: 統計表示、スキル・グレードマップ、活動ログ表示
  - 状態: ⏳ 未チェック

- [ ] **2. スキル管理一覧**
  - URL: `/salary/admin/skills/`
  - ビュー: `AdminSkillListView`
  - チェック項目: スキル一覧表示、削除ボタン動作、習得者数表示
  - 状態: ⏳ 未チェック

- [ ] **3. グレード管理一覧**
  - URL: `/salary/admin/grades/`
  - ビュー: `AdminGradeListView`
  - チェック項目: グレード一覧表示、削除ボタン動作、所属者数表示
  - 状態: ⏳ 未チェック

- [ ] **4. ユーザー管理一覧**
  - URL: `/salary/admin/user-management/`
  - ビュー: `AdminUserManagementView`
  - チェック項目: ユーザー一覧、検索・フィルタ機能、グレード表示
  - 状態: ⏳ 未チェック

- [ ] **5. 申告承認一覧**
  - URL: `/salary/admin/applications/`
  - ビュー: `AdminApplicationListView`
  - チェック項目: 承認待ち申告一覧、一括操作ボタン、個別遷移
  - 状態: ⏳ 未チェック

### 🎯 **Phase 2: 作成・編集画面（優先度: 中）**

- [ ] **6. スキル作成**
  - URL: `/salary/admin/skills/create/`
  - ビュー: `AdminSkillCreateView`
  - チェック項目: フォーム表示、作成処理、リダイレクト

- [ ] **7. スキル編集**
  - URL: `/salary/admin/skills/<id>/edit/`
  - ビュー: `AdminSkillEditView`
  - チェック項目: フォーム初期値、更新処理、習得者数表示

- [ ] **8. グレード作成**
  - URL: `/salary/admin/grades/create/`
  - ビュー: `AdminGradeCreateView`
  - チェック項目: フォーム表示、作成処理、リダイレクト

- [ ] **9. グレード編集**
  - URL: `/salary/admin/grades/<id>/edit/`
  - ビュー: `AdminGradeEditView`
  - チェック項目: フォーム初期値、更新処理、所属者数表示

- [ ] **10. 申告個別審査**
  - URL: `/salary/admin/applications/<id>/review/`
  - ビュー: `AdminApplicationReviewView`
  - チェック項目: 申告詳細表示、承認・却下ボタン、ユーザー情報表示

- [ ] **11. ユーザー詳細管理**
  - URL: `/salary/admin/user-management/<user_id>/`
  - ビュー: `AdminUserDetailView`
  - チェック項目: ユーザー詳細、習得スキル、グレード変更機能

### 🎯 **Phase 3: 詳細表示画面（優先度: 中）**

- [ ] **12. スキル習得者一覧**
  - URL: `/salary/admin/skills/<id>/holders/`
  - ビュー: `AdminSkillHoldersView`
  - チェック項目: 習得者一覧表示、取消ボタン動作

- [ ] **13. グレード所属者一覧**
  - URL: `/salary/admin/grades/<id>/members/`
  - ビュー: `AdminGradeMembersView`
  - チェック項目: 所属者一覧表示、履歴表示

### 🎯 **Phase 4: API機能（優先度: 高）**

- [ ] **14. スキル削除API**
  - URL: `/salary/admin/skills/<id>/delete/`
  - チェック項目: 削除処理、習得者がいる場合の処理

- [ ] **15. スキル取消API**
  - URL: `/salary/admin/skills/api/holder-revoke/`
  - チェック項目: 習得取消処理、ログ記録

- [ ] **16. グレード削除API**
  - URL: `/salary/admin/grades/<id>/delete/`
  - チェック項目: 削除処理、所属者がいる場合のエラー

- [ ] **17. スキル付与API**
  - URL: `/salary/admin/user-management/api/grant-skill/`
  - チェック項目: 手動付与処理、重複チェック

- [ ] **18. ユーザースキル取消API**
  - URL: `/salary/admin/user-management/api/revoke-skill/`
  - チェック項目: 取消処理、ログ記録

- [ ] **19. グレード変更API**
  - URL: `/salary/admin/user-management/api/change-grade/`
  - チェック項目: グレード変更処理、履歴作成

- [ ] **20. 一括承認API**
  - URL: `/salary/admin/applications/api/bulk-approve/`
  - チェック項目: 複数申告の一括承認、UserSkill作成

- [ ] **21. 一括却下API**
  - URL: `/salary/admin/applications/api/bulk-reject/`
  - チェック項目: 複数申告の一括却下、ログ記録

- [ ] **22. 個別承認API**
  - URL: `/salary/admin/applications/api/<id>/approve/`
  - チェック項目: 個別承認処理、UserSkill作成

- [ ] **23. 個別却下API**
  - URL: `/salary/admin/applications/api/<id>/reject/`
  - チェック項目: 個別却下処理、コメント保存

## 🔧 チェック方法

### 各画面でのチェック項目

1. **画面表示チェック**
   - [ ] ページが正常にロードされる
   - [ ] レイアウトが正しく表示される
   - [ ] データが正しく表示される

2. **機能動作チェック**
   - [ ] ボタン・リンクが動作する
   - [ ] フォーム送信が正しく処理される
   - [ ] APIリクエストが正しく処理される

3. **エラーハンドリングチェック**
   - [ ] 権限エラーが適切に処理される
   - [ ] バリデーションエラーが表示される
   - [ ] サーバーエラーが適切に処理される

### チェック状況記録

- ⏳ **未チェック**: まだ確認していない
- ✅ **正常**: 問題なく動作する
- ⚠️ **要修正**: 軽微な問題あり
- ❌ **エラー**: 重大な問題で動作しない
- 🔧 **修正中**: 現在修正作業中

## 📝 問題発見時の記録フォーマット

```markdown
### [画面名] エラー詳細
- **URL**: [URL]
- **エラー内容**: [詳細なエラー内容]
- **再現手順**: [エラーが発生する手順]
- **期待される動作**: [本来の動作]
- **修正方針**: [修正案]
```

## 🎯 現在の作業状況

**現在作業中**: Phase 1 - メイン管理画面（1-5）から順番にチェック開始
**次の予定**: Phase 2 - 作成・編集画面のチェック

---

*最終更新: 2025-09-26*