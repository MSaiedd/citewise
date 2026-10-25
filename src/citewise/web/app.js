const $ = (id) => document.getElementById(id);
async function request(path, method = 'GET', body) {
  const response = await fetch(path, {method, headers: {'Authorization': `Bearer ${$('token').value}`, 'Content-Type': 'application/json'}, body: body ? JSON.stringify(body) : undefined});
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail));
  return data;
}
async function busy(form, target, action) {
  const button = form.querySelector('button'); button.disabled = true; target.textContent = 'Working…';
  try { await action(); } catch (error) { target.textContent = error.message; } finally { button.disabled = false; }
}
$('ingest').addEventListener('submit', (event) => {
  event.preventDefault(); busy(event.target, $('ingest-result'), async () => {
    const result = await request('/documents', 'POST', {title: $('title').value, text: $('text').value});
    $('ingest-result').textContent = `Saved ${result.title} as ${result.chunks} chunks.`;
  });
});
$('list').addEventListener('click', async () => {
  try { $('documents').textContent = JSON.stringify(await request('/documents'), null, 2); }
  catch (error) { $('documents').textContent = error.message; }
});
$('query').addEventListener('submit', (event) => {
  event.preventDefault(); busy(event.target, $('answer'), async () => {
    const result = await request('/query', 'POST', {question: $('question').value});
    $('answer').replaceChildren();
    const answer = document.createElement('p'); answer.textContent = result.answer; $('answer').append(answer);
    const meta = document.createElement('p'); meta.className = 'muted'; meta.textContent = `${result.backend} · ${result.latency_ms} ms · ${result.abstained ? 'No evidence' : 'Evidence found'}`; $('answer').append(meta);
    for (const citation of result.citations) {
      const source = document.createElement('pre');
      // Document content is untrusted: render text, never HTML.
      source.textContent = `${citation.title} · lines ${citation.line_start}–${citation.line_end}\n${citation.text}`; $('answer').append(source);
    }
  });
});
