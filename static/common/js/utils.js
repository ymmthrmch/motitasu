// timeclock共通ユーティリティ関数

/**
 * プログレスバーのアニメーション
 */
function animateProgressBar() {
    const progressBars = document.querySelectorAll('.progress-bar');
    progressBars.forEach(bar => {
        const achievement = parseFloat(bar.getAttribute('data-achievement'));
        if (!isNaN(achievement)) {
            setTimeout(() => {
                const width = Math.min(achievement, 100);
                bar.style.width = width + '%';
            }, 100);
        }
    });
}

/**
 * 数値のアニメーション表示
 */
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

/**
 * ツールチップの初期化（Bootstrap 5.3）
 */
function initializeTooltips() {
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));
}