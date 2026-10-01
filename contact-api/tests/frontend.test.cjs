// DOM-level form checks. Network responses are mocked; no real email is sent.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { JSDOM } = require('jsdom');
const root = path.resolve(__dirname, '../..');
const html = fs.readFileSync(path.join(root, 'contact.html'), 'utf8');
const js = fs.readFileSync(path.join(root, 'contact.js'), 'utf8');
const tick = () => new Promise(resolve => setImmediate(resolve));
const reply = (status, body) => ({ok: status >= 200 && status < 300, status, json: async () => body});

async function setup(responses) {
  const dom = new JSDOM(html, {url: 'https://sama-transports.com/contact.html?service=Pipe%20Transportation', runScripts: 'outside-only'});
  const { window } = dom;
  const calls = [];
  window.fetch = async (url, opts) => {
    calls.push({ url: String(url), opts });
    const next = responses.shift();
    if (next instanceof Error) throw next;
    if (typeof next === 'function') return next();
    assert.ok(next, 'Unexpected network call');
    return next;
  };
  window.eval(js);
  await tick();
  const form = window.document.querySelector('#request-form');
  for (const name of ['full_name', 'company', 'phone','loading_location','delivery_location']) form.elements[name].value = 'Test';
  form.elements.email.value = 'client@example.com';
  const submit = () => form.dispatchEvent(new window.Event('submit', {bubbles:true,cancelable:true}));
  return {window, form, calls, submit, close: () => window.close(),
    button: form.querySelector('button[type=submit]'),
    error: window.document.querySelector('#request-error'),
    status: window.document.querySelector('#request-status')};
}
const token = () => reply(200,{ok:true,token:'signed-token',expires_in:3600});

test('service selection, gated activation and success',async () => {
  const s = await setup([token(),reply(200,{ok:true,reference:'abc123'})]);
  try {
    assert.equal(s.form.elements.service.value,'Pipe Transportation');
    assert.equal(s.button.disabled,false);
    assert.equal(s.form.elements.document.disabled,false);
    s.submit(); await tick();
    assert.equal(s.calls[1].url,'https://forms.sama-transports.com/v1/contact');
    assert.equal(s.calls[1].opts.credentials,'omit');
    assert.equal(s.calls[1].opts.headers['X-Form-Token'],'signed-token');
    assert.equal(s.calls[1].opts.body.get('service'),'Pipe Transportation');
    assert.equal(s.form.elements.email.value,'');
    assert.match(s.status.textContent,/accepted for email delivery.*abc123/);
    assert.equal(s.button.disabled,true);
  } finally {s.close();}
});

test('unavailable API keeps submit disabled and shows email fallback',async () => {
  const s = await setup([new Error('network down')]);
  try {
    assert.equal(s.button.disabled,true);
    assert.match(s.window.document.querySelector('#request-availability').textContent,/operations@sama-transports.com/);
    s.submit(); await tick();
    assert.equal(s.calls.length,1);
  } finally {s.close();}
});

test('SMTP refusal preserves input and permits a retry',async () => {
  const s = await setup([token(),reply(502,{ok:false,message:'SMTP unavailable'})]);
  try {
    s.submit(); await tick();
    assert.equal(s.form.elements.email.value,'client@example.com');
    assert.equal(s.error.textContent,'SMTP unavailable');
    assert.equal(s.button.disabled,false);
    assert.doesNotMatch(s.status.textContent,/accepted/);
  } finally {s.close();}
});

test('lost response retries with the original token and no extra token fetch',async () => {
  const s = await setup([token(),new Error('lost response'),reply(200,{ok:true,reference:'same-request'})]);
  try {
    s.submit(); await tick();
    assert.equal(s.form.elements.email.value,'client@example.com');
    assert.match(s.error.textContent,/could not confirm/);
    s.submit(); await tick();
    assert.equal(s.calls.length,3);
    assert.equal(s.calls[1].opts.headers['X-Form-Token'],s.calls[2].opts.headers['X-Form-Token']);
    assert.match(s.status.textContent,/same-request/);
  } finally {s.close();}
});

test('uncertain delivery closes sending and retains entered information',async () => {
  const s = await setup([token(),reply(409,{ok:false,code:'status_unknown',reference:'ref-unknown',message:'Check status'})]);
  try {
    s.submit(); await tick();
    assert.equal(s.button.disabled,true);
    assert.equal(s.form.elements.email.value,'client@example.com');
    assert.match(s.error.textContent,/ref-unknown/);
    s.submit(); await tick(); assert.equal(s.calls.length,2);
  } finally {s.close();}
});

test('double click sends only one request while busy',async () => {
  let done;
  const waiting = new Promise(resolve => {done=resolve;});
  const s = await setup([token(),() => waiting]);
  try {
    s.submit(); s.submit();
    assert.equal(s.calls.length,2);
    done(reply(200,{ok:true,reference:'once'})); await tick();
    assert.equal(s.calls.length,2);
  } finally {s.close();}
});

test('oversized document is rejected before POST',async () => {
  const s = await setup([token()]);
  try {
    Object.defineProperty(s.form.elements.document,'files',{value:[{name:'cargo.pdf',size:5*1024*1024+1}]});
    s.submit(); await tick();
    assert.equal(s.calls.length,1);
    assert.match(s.error.textContent,/5 MB/);
  } finally {s.close();}
});
