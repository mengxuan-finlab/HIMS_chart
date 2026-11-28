(() => {
  const allowedParents = new Set([
    'https://doncaibao.com', 'https://www.doncaibao.com',
    'http://localhost:3000', 'http://localhost:5173', 'http://localhost:5500',
    'http://localhost:8080', 'http://127.0.0.1:3000', 'http://127.0.0.1:5173',
    'http://127.0.0.1:5500', 'http://127.0.0.1:8080'
  ]);
  const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
  const text = value => typeof value === 'string' && value.length <= 10000 ? value : '';
  const strings = value => Array.isArray(value) ? value.slice(0, 30).filter(item => text(item)) : [];

  function normalizeReport(report, symbol, market) {
    try {
      if (!object(report) || report.symbol !== symbol || JSON.stringify(report).length > 1000000) return null;
      const diagnostics = { invalidSeries: 0, invalidPoints: 0, invalidInsights: 0, discardedViews: 0 };
      const cleanView = view => {
        if (!object(view) || !object(view.data)) return null;
        const entries = Object.entries(view.data);
        if (entries.length > 60) return null;
        const data = {};
        for (const [key, points] of entries) {
          if (!/^[a-zA-Z0-9_]+$/.test(key) || ['__proto__', 'constructor', 'prototype'].includes(key)
              || !Array.isArray(points) || points.length > 2000) {
            diagnostics.invalidSeries++;
            continue;
          }
          data[key] = points.filter(point => {
            const valid = object(point) && typeof point.date === 'string'
              && /^(?:TTM|\d{4}-\d{2}(?:-\d{2})?)$/.test(point.date)
              && (point.value === null || (typeof point.value === 'number' && Number.isFinite(point.value)));
            if (!valid) diagnostics.invalidPoints++;
            return valid;
          });
        }
        const source = object(view.ai) ? view.ai : {};
        const ai = { one_liner: text(source.one_liner), risks: strings(source.risks), by_metric: {} };
        if (market === 'TW') ai.highlights = strings(source.highlights);
        if (object(source.by_metric)) {
          for (const [key, item] of Object.entries(source.by_metric).slice(0, 60)) {
            if (!/^[a-zA-Z0-9_]+$/.test(key) || ['__proto__', 'constructor', 'prototype'].includes(key) || !object(item)) {
              diagnostics.invalidInsights++;
              continue;
            }
            ai.by_metric[key] = { summary: text(item.summary), bullets: strings(item.bullets),
              related_reasons: strings(item.related_reasons) };
          }
        }
        return { data, ai, periods: object(view.periods) ? view.periods : {} };
      };
      const usable = view => view && Object.values(view.data).some(points => points.some(point => Number.isFinite(point.value)));
      let root = cleanView(report);
      const views = {};
      if (market === 'US' && report.financialFormat === 'dual-period-v1' && object(report.views)) {
        for (const period of ['quarter', 'annual']) {
          const view = report.views[period];
          if (!object(view) || !object(view.periods)
              || !['income', 'eps', 'balance', 'cashFlow'].every(key => view.periods[key] === period)
              || !(period === 'quarter' ? ['ttm', 'quarter_ttm'] : ['annual']).includes(view.periods.metrics)) {
            diagnostics.discardedViews++;
            continue;
          }
          const cleaned = cleanView(view);
          if (cleaned) views[period] = cleaned;
          else diagnostics.discardedViews++;
        }
      }
      if (!usable(root)) root = [views.quarter, views.annual].find(usable);
      if (!usable(root)) return null;
      const { views: unusedViews, ...metadata } = report;
      const result = { ...metadata, ...root };
      if (views.quarter && views.annual) result.views = views;
      if (Object.values(diagnostics).some(Boolean)) console.warn('[財報圖表部分資料略過]', diagnostics);
      return result;
    } catch { return null; }
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
            || data.type !== 'dcb:financial-report' || data.version !== 1 || data.channel !== channel) return;
        const report = normalizeReport(data.report, symbol, market);
        if (!report) {
          cleanup();
          reject(new Error('這份報告目前沒有可顯示的圖表資料。'));
          return;
        }
        cleanup();
        resolve(report);
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
