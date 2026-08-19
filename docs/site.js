const observer = new IntersectionObserver((entries) => {
  entries.forEach((entry) => {
    if (entry.isIntersecting) {
      entry.target.classList.add('is-visible');
      observer.unobserve(entry.target);
    }
  });
}, { threshold: 0.12 });

document.querySelectorAll('.reveal').forEach((element) => observer.observe(element));

const countElement = document.querySelector('[data-count]');
if (countElement) {
  const target = Number(countElement.dataset.count);
  let rendered = false;
  const countObserver = new IntersectionObserver((entries) => {
    if (entries[0].isIntersecting && !rendered) {
      rendered = true;
      const started = performance.now();
      const duration = 900;
      const tick = (now) => {
        const progress = Math.min((now - started) / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3);
        countElement.textContent = Math.round(target * eased).toLocaleString('ko-KR');
        if (progress < 1) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
      countObserver.disconnect();
    }
  }, { threshold: 0.4 });
  countObserver.observe(countElement);
}
