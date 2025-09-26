// 給与グレード管理画面のJavaScript

document.addEventListener('DOMContentLoaded', function() {
    
    // === グレード削除機能 ===
    const deleteButtons = document.querySelectorAll('.delete-grade-btn');
    const deleteModal = document.getElementById('deleteModal');
    const deleteModalBody = document.getElementById('deleteModalBody');
    const confirmDeleteBtn = document.getElementById('confirmDeleteBtn');
    let currentGradeId = null;

    // 削除ボタンクリック時の処理
    deleteButtons.forEach(button => {
        button.addEventListener('click', function() {
            const gradeId = this.dataset.gradeId;
            const gradeName = this.dataset.gradeName;
            const membersCount = parseInt(this.dataset.membersCount) || 0;

            currentGradeId = gradeId;
            
            // モーダル内容を設定
            let modalContent = `
                <div class="text-center mb-4">
                    <i class="bi bi-exclamation-triangle text-warning" style="font-size: 3rem;"></i>
                </div>
                <h5 class="text-center mb-3">「${gradeName}」を削除しますか？</h5>
            `;
            
            if (membersCount > 0) {
                modalContent += `
                    <div class="alert alert-danger">
                        <i class="bi bi-exclamation-triangle"></i>
                        <strong>注意:</strong> このグレードには現在 <strong>${membersCount}人</strong> が所属しています。<br>
                        削除すると、これらのユーザーのグレード設定が解除されます。
                    </div>
                `;
            }
            
            modalContent += `
                <p class="text-muted text-center">
                    この操作は取り消せません。本当に削除しますか？
                </p>
            `;

            deleteModalBody.innerHTML = modalContent;

            // Bootstrap 5のモーダル表示
            const modal = new bootstrap.Modal(deleteModal);
            modal.show();
        });
    });

    // 削除確認ボタンクリック時の処理
    if (confirmDeleteBtn) {
        confirmDeleteBtn.addEventListener('click', function() {
            if (!currentGradeId) return;

            // ボタンを無効化して処理中表示
            confirmDeleteBtn.disabled = true;
            confirmDeleteBtn.innerHTML = '<i class="bi bi-hourglass-split"></i> 削除中...';

            // APIを呼び出してグレード削除
            fetch(`/salary/admin/grades/${currentGradeId}/delete/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken()
                }
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
                    confirmDeleteBtn.disabled = false;
                    confirmDeleteBtn.innerHTML = '削除';
                }
            })
            .catch(error => {
                console.error('削除エラー:', error);
                alert('削除処理中にエラーが発生しました。');
                
                // ボタンを再有効化
                confirmDeleteBtn.disabled = false;
                confirmDeleteBtn.innerHTML = '削除';
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