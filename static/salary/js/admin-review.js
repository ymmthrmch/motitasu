// 申告審査画面のJavaScript

document.addEventListener('DOMContentLoaded', function() {
    const reviewForm = document.getElementById('reviewForm');
    const applicationId = reviewForm.dataset.applicationId;
    const userName = reviewForm.dataset.userName;
    const skillName = reviewForm.dataset.skillName;
    
    const approveBtn = document.getElementById('approveBtn');
    const rejectBtn = document.getElementById('rejectBtn');
    const reviewComment = document.getElementById('reviewComment');
    
    // 初期化
    initializeReviewActions();
    
    // 審査アクションの初期化
    function initializeReviewActions() {
        // 承認ボタンのクリックイベント
        approveBtn.addEventListener('click', function() {
            showConfirmModal(
                '承認確認',
                `${userName} さんの「${skillName}」スキル申告を承認しますか？`,
                'success',
                () => performAction('approve')
            );
        });
        
        // 却下ボタンのクリックイベント
        rejectBtn.addEventListener('click', function() {
            showConfirmModal(
                '却下確認',
                `${userName} さんの「${skillName}」スキル申告を却下しますか？`,
                'danger', 
                () => performAction('reject')
            );
        });
    }
    
    // 確認モーダルを表示
    function showConfirmModal(title, message, type, onConfirm) {
        const modal = new bootstrap.Modal(document.getElementById('confirmModal'));
        const modalTitle = document.getElementById('confirmModalLabel');
        const modalBody = document.getElementById('confirmModalBody');
        const confirmBtn = document.getElementById('confirmActionBtn');
        
        modalTitle.textContent = title;
        modalBody.textContent = message;
        
        // ボタンの種別に応じてクラスを設定
        if (type === 'success') {
            confirmBtn.className = 'btn-gradient-success';
        } else if (type === 'danger') {
            confirmBtn.className = 'btn-gradient-danger';
        } else {
            confirmBtn.className = 'btn-gradient-primary';
        }
        
        // 前のイベントリスナーを削除
        const newConfirmBtn = confirmBtn.cloneNode(true);
        confirmBtn.parentNode.replaceChild(newConfirmBtn, confirmBtn);
        
        // 新しいイベントリスナーを追加
        newConfirmBtn.addEventListener('click', () => {
            modal.hide();
            onConfirm();
        });
        
        modal.show();
    }
    
    // 処理の実行
    async function performAction(action) {
        const processingModal = new bootstrap.Modal(document.getElementById('processingModal'));
        const comment = reviewComment.value.trim();
        
        try {
            // 処理中モーダルを表示
            processingModal.show();
            
            // ボタンを無効化
            approveBtn.disabled = true;
            rejectBtn.disabled = true;
            
            const response = await fetch(`/salary/admin/applications/api/${applicationId}/${action}/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken()
                },
                body: JSON.stringify({ comment: comment })
            });
            
            const result = await response.json();
            
            if (result.status === 'success') {
                // 成功メッセージを表示
                showSuccessMessage(action === 'approve' ? '承認' : '却下');
                
                // 1.5秒後に一覧画面に戻る
                setTimeout(() => {
                    window.location.href = '/salary/admin/applications/';
                }, 1500);
            } else {
                processingModal.hide();
                enableButtons();
                showAlert(`処理に失敗しました: ${result.message}`, 'danger');
            }
        } catch (error) {
            processingModal.hide();
            enableButtons();
            console.error('Error:', error);
            showAlert('通信エラーが発生しました。', 'danger');
        }
    }
    
    // 成功メッセージを表示
    function showSuccessMessage(actionType) {
        const processingModal = bootstrap.Modal.getInstance(document.getElementById('processingModal'));
        const modalBody = processingModal._element.querySelector('.modal-body');
        
        modalBody.innerHTML = `
            <div class="text-center py-4">
                <i class="bi bi-check-circle-fill text-success mb-3" style="font-size: 3rem;"></i>
                <div class="h5 mb-2">${actionType}完了</div>
                <div class="text-muted">一覧画面に戻ります...</div>
            </div>
        `;
    }
    
    // ボタンを有効化
    function enableButtons() {
        approveBtn.disabled = false;
        rejectBtn.disabled = false;
    }
    
    // アラート表示
    function showAlert(message, type) {
        const alertContainer = document.querySelector('.container-fluid');
        const alert = document.createElement('div');
        alert.className = `alert alert-${type} alert-dismissible fade show`;
        alert.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        alertContainer.insertBefore(alert, alertContainer.firstChild);
        
        // 自動で閉じる
        setTimeout(() => {
            if (alert.parentNode) {
                alert.remove();
            }
        }, 5000);
    }
    
    // ページ離脱時の確認（処理中の場合）
    window.addEventListener('beforeunload', function(e) {
        if (approveBtn.disabled || rejectBtn.disabled) {
            e.preventDefault();
            e.returnValue = '処理中です。このページを離れますか？';
        }
    });
});