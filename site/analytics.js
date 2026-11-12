'use strict';
// Vercel's official static-site queue + script. Page views only; no custom properties.
(() => {
  window.va = window.va || function () { (window.vaq = window.vaq || []).push(arguments); };
  const pages = new Set(['/', '/index.html', '/eval-guide.html', '/human-review.html']);
  window.va('beforeSend', event => {
    if (!event || event.type !== 'pageview') return null;
    try {
      const url = new URL(event.url, window.location.origin);
      if (url.origin !== window.location.origin || !pages.has(url.pathname)) return null;
      // Never send search terms, email/token query strings, skill hashes or custom data.
      return {type: 'pageview', url: url.origin + (url.pathname === '/index.html' ? '/' : url.pathname)};
    } catch { return null; }
  });
  // Local tests/previews do not send visits into the production project's analytics.
  if (!['skillwire.net', 'www.skillwire.net'].includes(window.location.hostname)) return;
  if (document.querySelector('script[data-skillwire-analytics]')) return;
  const script = document.createElement('script');
  script.defer = true;
  script.src = '/_vercel/insights/script.js';
  script.dataset.skillwireAnalytics = 'official';
  document.head.append(script);
})();
