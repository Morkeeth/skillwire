/* Opens the catalog with a skill name from a chart link, for example /search?q=animate. */
(function () {
  'use strict';
  const wanted = new URLSearchParams(location.search).get('q');
  if (!wanted) return;
  const box = document.querySelector('#query');
  if (!box) return;
  let tries = 0;
  const timer = setInterval(() => {
    tries += 1;
    const loaded = document.querySelector('#skill-count')?.textContent !== '0';
    if (!loaded && tries < 100) return;
    clearInterval(timer);
    box.value = wanted.slice(0, 80);
    box.dispatchEvent(new Event('input', {bubbles: true}));
  }, 100);
})();
