(() => {
  const allowedParents = new Set([
    'https://doncaibao.com', 'https://www.doncaibao.com',
    'http://localhost:3000', 'http://localhost:5173', 'http://localhost:5500',
    'http://localhost:8080', 'http://127.0.0.1:3000', 'http://127.0.0.1:5173',
    'http://127.0.0.1:5500', 'http://127.0.0.1:8080'
  ]);
  const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
  const strings = value => Array.isArray(value) && value.length <= 30
    && value.every(item => typeof item === 'string' && item.length <= 10000);

  function validReport(report, symbol, market) {
    try {
      if (!object(report) || report.symbol !== symbol || !object(report.data) || !object(report.ai)
          || JSON.stringify(report).length > 1000000) return false;
      const series = Object.entries(report.data);
      if (!series.length || series.length > 60 || !series.every(([key, points]) =>
        /^[a-zA-Z0-9_]+$/.test(key) && Array.isArray(points) && points.length <= 2000
        && points.every(point => object(point) && typeof point.date === 'string'
          && /^(?:TTM|\d{4}-\d{2}(?:-\d{2})?)$/.test(point.date)
          && (point.value === null || (typeof point.value === 'number' && Number.isFinite(point.value)))))) return false;
      if (typeof report.ai.one_liner !== 'string' || report.ai.one_liner.length > 10000) return false;
      if (report.ai.risks !== undefined && !strings(report.ai.risks)) return false;
      if (market === 'TW') return report.ai.highlights === undefined || strings(report.ai.highlights);
      if (!object(report.ai.by_metric) || Object.keys(report.ai.by_metric).length > 60) return false;
      return Object.values(report.ai.by_metric).every(item => object(item)
        && (item.summary === undefined || (typeof item.summary === 'string' && item.summary.length <= 10000))
        && (item.bullets === undefined || strings(item.bullets))
        && (item.related_reasons === undefined || strings(item.related_reasons)));
    } catch { return false; }
  }

  function receiveReport(market, symbol) {
    return new Promise((resolve, reject) => {
      const params = new URLSearchParams(window.location.search);
      const parentOrigin = params.get('parentOrigin');
      const channel = params.get('channel');
      const symbolPattern = market === 'TW' ? /^[0-9]{4}(?:\.(?:TW|TWO))?$/ : /^[A-Z][A-Z0-9.^-]{0,19}$/;
      if (window.parent === window || !allowedParents.has(parentOrigin)
          || !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(channel || '')
          || !symbolPattern.test(symbol)) {
        reject(new Error('請從懂才抱主網站的財報分析頁開啟此報告。'));
        return;
      }
      const cleanup = () => {
        window.removeEventListener('message', onMessage);
        clearInterval(retry);
        clearTimeout(timeout);
      };
      const onMessage = event => {
        const data = event.data;
        if (event.origin !== parentOrigin || event.source !== window.parent || !object(data)
            || data.type !== 'dcb:financial-report' || data.version !== 1 || data.channel !== channel
            || !validReport(data.report, symbol, market)) return;
        cleanup();
        resolve(data.report);
      };
      const ready = () => window.parent.postMessage({ type: 'dcb:chart-ready', version: 1, channel, symbol }, parentOrigin);
      window.addEventListener('message', onMessage);
      const retry = setInterval(ready, 1000);
      const timeout = setTimeout(() => {
        cleanup();
        reject(new Error('財報資料傳送逾時，請回主網站重新開啟報告。'));
      }, 20000);
      ready();
    });
  }

  // Clear credentials stored by older chart pages; new charts never create sessions.
  try { window.localStorage.removeItem('sb-zlkexplsleznuebighte-auth-token'); } catch { /* Storage may be blocked. */ }
  window.DcbReportBridge = { receiveReport };
})();
