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
  let rendered = false;
  const countObserver = new IntersectionObserver((entries) => {
    if (entries[0].isIntersecting && !rendered) {
      rendered = true;
      const target = Number(countElement.dataset.count);
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

const byId = (id) => document.getElementById(id);
const fmtDate = (value) => value ? value.replaceAll('-', '.') : '';

async function applyLatestData() {
  try {
    const response = await fetch(`site-data.json?v=${Date.now()}`, { cache: 'no-store' });
    if (!response.ok) throw new Error(`site-data.json HTTP ${response.status}`);
    const data = await response.json();
    const summary = data.summary;
    if (!summary) return;

    const recordCount = Number(summary.recordCount).toLocaleString('ko-KR');
    const record = byId('stat-record-count');
    if (record) {
      record.dataset.count = String(summary.recordCount);
      record.textContent = recordCount;
    }
    const period = byId('stat-period');
    if (period) period.textContent = `${summary.periodStart.slice(0, 4)}–${summary.periodEnd.slice(0, 4)}`;
    const maxMagnitude = byId('stat-max-magnitude');
    if (maxMagnitude) maxMagnitude.textContent = `M ${Number(summary.maxMagnitude).toFixed(1)}`;
    const maxDate = byId('stat-max-date');
    if (maxDate) maxDate.textContent = fmtDate(summary.maxMagnitudeDate);
    const meanMagnitude = byId('stat-mean-magnitude');
    if (meanMagnitude) meanMagnitude.textContent = `M ${Number(summary.meanMagnitude).toFixed(2)}`;
    const depthMean = byId('stat-depth-mean');
    if (depthMean && summary.depthMeanKm !== null) depthMean.textContent = `${Number(summary.depthMeanKm).toFixed(1)} km`;
    const depthNote = byId('stat-depth-note');
    if (depthNote) depthNote.textContent = `유효값 ${Number(summary.depthValidShare).toFixed(1)}% 기준`;
    const caption = byId('latest-record-caption');
    if (caption) caption.textContent = `${recordCount} RECORDS / KMA API`;
    ['hero-record-count', 'story-record-count'].forEach((id) => {
      const element = byId(id);
      if (element) element.textContent = recordCount;
    });
    const storyDate = byId('story-analysis-date');
    if (storyDate) storyDate.textContent = fmtDate(summary.periodEnd);
    const status = byId('latest-status');
    if (status) status.textContent = `마지막 기록 기준 ${fmtDate(summary.periodEnd)}`;

    const version = encodeURIComponent(data.generatedAt || summary.periodEnd || 'latest');
    ['latest-overview-image', 'latest-yearly-image'].forEach((id) => {
      const image = byId(id);
      if (image) image.src = `${image.src.split('?')[0]}?v=${version}`;
    });
  } catch (error) {
    console.info('Latest earthquake data is unavailable; using the static page values.', error);
  }
}

applyLatestData();
