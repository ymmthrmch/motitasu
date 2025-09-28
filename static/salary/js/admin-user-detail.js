// ユーザー詳細管理画面のJavaScript

document.addEventListener('DOMContentLoaded', function() {
    
    // === グレード変更機能 ===
    const gradeChangeForm = document.getElementById('gradeChangeForm');
    if (gradeChangeForm) {
        gradeChangeForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const userId = this.dataset.userId;
            const newGradeSelect = document.getElementById('newGrade');
            const newGradeId = newGradeSelect.value;
            const newGradeName = newGradeSelect.options[newGradeSelect.selectedIndex].text;
            
            if (!newGradeId) {
                alert('グレードを選択してください。');
                return;
            }
            
            // 確認ダイアログ
            if (!confirm(`グレードを「${newGradeName}」に変更しますか？`)) {
                return;
            }
            
            const submitBtn = this.querySelector('button[type="submit"]');
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i class="bi bi-hourglass-split"></i> 変更中...';
            
            // API呼び出し
            fetch('/salary/admin/user-management/api/change-grade/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken()
                },
                body: JSON.stringify({
                    user_id: userId,
                    grade_id: newGradeId
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    // 成功時はページリロード
                    window.location.reload();
                } else {
                    alert('エラーが発生しました: ' + (data.message || '不明なエラー'));
                    
                    // ボタンを再有効化
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = '<i class="bi bi-arrow-up-right"></i> グレード変更';
                }
            })
            .catch(error => {
                console.error('グレード変更エラー:', error);
                alert('処理中にエラーが発生しました。');
                
                // ボタンを再有効化
                submitBtn.disabled = false;
                submitBtn.innerHTML = '<i class="bi bi-arrow-up-right"></i> グレード変更';
            });
        });
    }
    
    // === スキル手動付与機能 ===
    const skillGrantForm = document.getElementById('skillGrantForm');
    if (skillGrantForm) {
        skillGrantForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const userId = this.dataset.userId;
            const skillSelect = document.getElementById('newSkill');
            const skillId = skillSelect.value;
            const skillName = skillSelect.options[skillSelect.selectedIndex].text;
            
            if (!skillId) {
                alert('スキルを選択してください。');
                return;
            }
            
            // 確認ダイアログ
            if (!confirm(`「${skillName}」を手動付与しますか？`)) {
                return;
            }
            
            const submitBtn = this.querySelector('button[type="submit"]');
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i class="bi bi-hourglass-split"></i> 付与中...';
            
            // API呼び出し
            fetch('/salary/admin/user-management/api/grant-skill/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken()
                },
                body: JSON.stringify({
                    user_id: userId,
                    skill_id: skillId
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    // 成功時はページリロード
                    window.location.reload();
                } else {
                    alert('エラーが発生しました: ' + (data.message || '不明なエラー'));
                    
                    // ボタンを再有効化
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = '<i class="bi bi-plus"></i> スキル付与';
                }
            })
            .catch(error => {
                console.error('スキル付与エラー:', error);
                alert('処理中にエラーが発生しました。');
                
                // ボタンを再有効化
                submitBtn.disabled = false;
                submitBtn.innerHTML = '<i class="bi bi-plus"></i> スキル付与';
            });
        });
    }
    
    // === スキル取消機能 ===
    const revokeButtons = document.querySelectorAll('.revoke-skill-btn');
    const revokeModal = document.getElementById('revokeSkillModal');
    const revokeModalBody = document.getElementById('revokeSkillModalBody');
    const confirmRevokeBtn = document.getElementById('confirmRevokeSkillBtn');
    let currentUserSkillId = null;
    
    revokeButtons.forEach(button => {
        button.addEventListener('click', function() {
            currentUserSkillId = this.dataset.userSkillId;
            const skillName = this.dataset.skillName;
            
            // モーダル内容を設定
            const modalContent = `
                <div class="text-center mb-4">
                    <i class="bi bi-exclamation-triangle text-warning" style="font-size: 3rem;"></i>
                </div>
                <h5 class="text-center mb-3">スキルを取り消しますか？</h5>
                <div class="text-center mb-4">
                    <strong>対象スキル:</strong> ${skillName}
                </div>
                <div class="alert alert-warning">
                    <i class="bi bi-exclamation-triangle"></i>
                    この操作により、ユーザーの「${skillName}」スキル習得記録が削除されます。
                </div>
                <p class="text-muted text-center">
                    この操作は取り消せません。本当に実行しますか？
                </p>
            `;
            
            revokeModalBody.innerHTML = modalContent;
            
            // Bootstrap 5のモーダル表示
            const modal = new bootstrap.Modal(revokeModal);
            modal.show();
        });
    });
    
    if (confirmRevokeBtn) {
        confirmRevokeBtn.addEventListener('click', function() {
            if (!currentUserSkillId) return;
            
            // ボタンを無効化して処理中表示
            confirmRevokeBtn.disabled = true;
            confirmRevokeBtn.innerHTML = '<i class="bi bi-hourglass-split"></i> 処理中...';
            
            // API呼び出し
            fetch('/salary/admin/user-management/api/revoke-skill/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken()
                },
                body: JSON.stringify({
                    user_skill_id: currentUserSkillId
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    // 成功時はページリロード
                    window.location.reload();
                } else {
                    alert('エラーが発生しました: ' + (data.message || '不明なエラー'));
                    
                    // ボタンを再有効化
                    confirmRevokeBtn.disabled = false;
                    confirmRevokeBtn.innerHTML = '取消実行';
                }
            })
            .catch(error => {
                console.error('スキル取消エラー:', error);
                alert('処理中にエラーが発生しました。');
                
                // ボタンを再有効化
                confirmRevokeBtn.disabled = false;
                confirmRevokeBtn.innerHTML = '取消実行';
            });
        });
    }
    
    // CSRFトークン取得関数（共通utilsを使用）
    function getCsrfToken() {
        // まず共通のgetCsrfToken関数を試す
        if (typeof window.getCsrfToken === 'function') {
            return window.getCsrfToken();
        }
        
        // フォールバック: トークンを直接取得
        const token = document.querySelector('[name=csrfmiddlewaretoken]');
        if (token) {
            return token.value;
        }
        
        // クッキーからの取得
        const name = 'csrftoken';
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
});