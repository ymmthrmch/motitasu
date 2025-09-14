function animateProgressBar() {
    const progressBars = document.querySelectorAll('.progress-bar');
    progressBars.forEach(bar => {
        const achievement = parseFloat(bar.getAttribute('data-achievement'));
        if (!isNaN(achievement)) {
            setTimeout(() => {
                const width = Math.min(achievement, 100);
                bar.style.width = width + '%';
            }, 500);
        }
    });
}

function animateValue(element, start, end, duration) {
    if (!element) return;

    const startTimestamp = Date.now();
    const step = () => {
        const timestamp = Date.now();
        const progress = Math.min((timestamp - startTimestamp) / duration, 1);
        const current = Math.floor(progress * (end - start) + start);
        element.textContent = current.toLocaleString() + (element.dataset.suffix || '');
        if (progress < 1) {
            window.requestAnimationFrame(step);
        }
    };
    window.requestAnimationFrame(step);
}

document.addEventListener('DOMContentLoaded', function () {
    // プログレスバーのアニメーション
    animateProgressBar();

    // カレンダーの日付クリックイベント（将来の拡張用）
    const calendarDays = document.querySelectorAll('.calendar-day.has-data');
    calendarDays.forEach(day => {
        day.addEventListener('click', function () {
            // 将来的に日別の詳細表示機能を追加可能
            console.log('Day clicked:', this);
        });
    });

    // カレンダーの月切り替え時のアニメーション
    const calendarCard = document.querySelector('.calendar-card');
    if (calendarCard) {
        calendarCard.style.opacity = '0';
        setTimeout(() => {
            calendarCard.style.transition = 'opacity 0.5s ease';
            calendarCard.style.opacity = '1';
        }, 100);
    }

    // サマリーカードの数値アニメーション
    const statsValues = document.querySelectorAll('.animate-value');
    statsValues.forEach(element => {
        const text = element.textContent;
        const match = text.match(/^(\d+)/);
        if (match) {
            const value = parseInt(match[1]);
            const suffix = text.replace(/^\d+/, '');
            element.dataset.suffix = suffix;
            animateValue(element, 0, value, 1000);
        }
    });

    // ツールチップの初期化（Bootstrap 5.3）
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));
});