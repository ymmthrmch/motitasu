// スキル習得者一覧画面のJavaScript

document.addEventListener('DOMContentLoaded', function() {
    
    // === スキル取消機能 ===
    const revokeButtons = document.querySelectorAll('.revoke-skill-btn');
    const revokeModal = document.getElementById('revokeModal');
    const revokeModalBody = document.getElementById('revokeModalBody');
    const confirmRevokeBtn = document.getElementById('confirmRevokeBtn');
    let currentUserId = null;
    let currentSkillId = null;

    // スキル取消ボタンクリック時の処理
    revokeButtons.forEach(button => {
        button.addEventListener('click', function() {
            currentUserId = this.dataset.userId;
            currentSkillId = this.dataset.skillId;
            const userName = this.dataset.userName;
            const skillName = this.dataset.skillName;
            
            // モーダル内容を設定
            const modalContent = `
                <div class="text-center mb-4">
                    <i class="bi bi-exclamation-triangle text-warning" style="font-size: 3rem;"></i>
                </div>
                <h5 class="text-center mb-3">スキル習得を取り消しますか？</h5>
                <div class="text-center mb-4">
                    <div class="mb-2">
                        <strong>対象者:</strong> ${userName}
                    </div>
                    <div class="mb-2">
                        <strong>スキル:</strong> ${skillName}
                    </div>
                </div>
                <div class="alert alert-warning">
                    <i class="bi bi-exclamation-triangle"></i>
                    この操作により、${userName}さんの「${skillName}」スキル習得記録が削除されます。
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

    // スキル取消確認ボタンクリック時の処理
    if (confirmRevokeBtn) {
        confirmRevokeBtn.addEventListener('click', function() {
            if (!currentUserId || !currentSkillId) return;

            // ボタンを無効化して処理中表示
            confirmRevokeBtn.disabled = true;
            confirmRevokeBtn.innerHTML = '<i class="bi bi-hourglass-split"></i> 処理中...';

            // APIを呼び出してスキル取消
            fetch('/salary/admin/skills/api/holder-revoke/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken()
                },
                body: JSON.stringify({
                    user_id: currentUserId,
                    skill_id: currentSkillId
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    // 成功時は画面リロード
                    window.location.reload();
                } else {
                    // エラー時はアラート表示
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

    // CSRFトークン取得関数
    function getCsrfToken() {
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