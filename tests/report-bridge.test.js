const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '..', 'report-bridge.js'), 'utf8');
const channel = '12345678-1234-1234-1234-123456789abc';

function setup() {
  let listener;
  const posts = [], warnings = [];
  const parent = { postMessage: (data, target) => posts.push({ data, target }) };
  const window = { parent, location: { search: `?parentOrigin=https%3A%2F%2Fdoncaibao.com&channel=${channel}` },
    localStorage: { removeItem() {} }, addEventListener: (_, fn) => { listener = fn; },
    removeEventListener: () => { listener = null; } };
  vm.runInNewContext(source, { window, URLSearchParams, setInterval: () => 1, clearInterval() {},
    setTimeout: () => 2, clearTimeout() {}, console: { warn: (...args) => warnings.push(args) } });
  return { window, parent, posts, warnings, send: (report, overrides = {}) => listener?.({
    origin: 'https://doncaibao.com', source: parent,
    data: { type: 'dcb:financial-report', version: 1, channel, report }, ...overrides }) };
}
function report() {
  return { symbol: 'GOOG', data: { revenue: [{ date: '2026-09-30', value: 100 }], roe: [] },
    ai: { one_liner: '', risks: [], by_metric: {} } };
}

test('partial numeric data survives malformed or missing insights and extra fields', async () => {
  const env = setup(), input = report();
  input.data.roe = [{ date: '2026-09-30', value: 'not-a-number' }];
  input.data.bad = 'missing';
  input.ai.by_metric = { revenue: { summary: '營收分析', bullets: ['正常', 123] }, extra: '未披露' };
  const promise = env.window.DcbReportBridge.receiveReport('US', 'GOOG');
  env.send(input);
  const result = await promise;
  assert.equal(result.data.revenue.length, 1);
  assert.equal(result.data.roe.length, 0);
  assert.equal(result.data.bad, undefined);
  assert.equal(result.ai.by_metric.revenue.bullets.length, 1);
  assert.equal(result.ai.by_metric.extra, undefined);
  assert.equal(env.warnings.length, 1);
});

test('missing AI does not hide real numeric data', async () => {
  const env = setup(), input = report(); delete input.ai;
  const promise = env.window.DcbReportBridge.receiveReport('US', 'GOOG'); env.send(input);
  const result = await promise;
  assert.equal(result.data.revenue[0].value, 100);
  assert.equal(result.ai.one_liner, '');
});

test('one invalid period view cannot reject the valid root report', async () => {
  const env = setup(), input = report();
  input.financialFormat = 'dual-period-v1';
  input.views = { annual: { data: {}, periods: { metrics: 'unknown' } } };
  const promise = env.window.DcbReportBridge.receiveReport('US', 'GOOG'); env.send(input);
  const result = await promise;
  assert.equal(result.data.revenue.length, 1);
  assert.equal(result.views, undefined);
});

test('valid annual data can recover a missing root dataset', async () => {
  const env = setup(), input = report(); input.data = {};
  input.financialFormat = 'dual-period-v1';
  input.views = { annual: { data: { revenue: [{ date: '2025-12-31', value: 400 }] },
    periods: { income: 'annual', eps: 'annual', balance: 'annual', cashFlow: 'annual', metrics: 'annual' } } };
  const promise = env.window.DcbReportBridge.receiveReport('US', 'GOOG'); env.send(input);
  const result = await promise;
  assert.equal(result.data.revenue[0].value, 400);
  assert.equal(result.periods.income, 'annual');
});

test('wrong origin, window and channel are ignored before the correct response', async () => {
  const env = setup(); let resolved = false;
  const promise = env.window.DcbReportBridge.receiveReport('US', 'GOOG').then(result => { resolved = true; return result; });
  env.send(report(), { origin: 'https://evil.test' });
  env.send(report(), { source: {} });
  env.send(report(), { data: { type: 'dcb:financial-report', version: 1, channel: 'wrong', report: report() } });
  await Promise.resolve(); assert.equal(resolved, false);
  env.send(report()); await promise;
  assert.equal(env.posts[0].target, 'https://doncaibao.com');
});

test('wrong symbol, oversized payload and no usable data still fail closed', async () => {
  for (const input of [{ ...report(), symbol: 'AAPL' }, { ...report(), note: 'x'.repeat(1000001) },
    { ...report(), data: { revenue: [] } }]) {
    const env = setup();
    const promise = env.window.DcbReportBridge.receiveReport('US', 'GOOG');
    env.send(input);
    await assert.rejects(promise, /沒有可顯示的圖表資料/);
  }
});
