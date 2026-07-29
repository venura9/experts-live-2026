/* Deck engine. Expects: .slide sections, and elements with ids
   rail, clock, dot, seg, pos, bar, notes, ntext, help.

   Keys:  right/space/pagedown  forward
          left/backspace/p      back
          home/end              first/last
          g or escape           overview grid, click a card to jump
          digits then enter     jump straight to a slide number
          n                     speaker notes
          t                     stop and reset the timer
          b                     toggle the status dot amber

   Click: right three quarters forward, left quarter back,
          right-click or shift-click back.
   ============================================================ */

const slides = [...document.querySelectorAll('.slide')];
let i = 0, started = null, notesOn = false, overviewOn = false, jumpBuf = '';

function show(n){
  i = Math.max(0, Math.min(slides.length - 1, n));
  // The timer used to be manual, so it sat at 00:00 unless you remembered to
  // press t. You will not remember. It now starts itself when you advance off
  // the title slide; t still stops and resets it.
  if(i > 0 && !started) started = Date.now();
  document.body.classList.toggle('timer-idle', !started);
  slides.forEach((s, k) => s.classList.toggle('on', k === i));
  const s = slides[i];
  document.getElementById('seg').textContent = s.dataset.seg || '';
  document.getElementById('pos').textContent = (i + 1) + ' / ' + slides.length + '   target ' + (s.dataset.t || '');
  document.getElementById('bar').style.width =
    ((i / (slides.length - 1)) * (window.innerWidth - 104)) + 'px';
  document.getElementById('ntext').textContent = s.dataset.notes || 'No notes.';
  document.getElementById('help').style.display = i === 0 ? 'block' : 'none';
  markOverview();
  syncHash(i + 1);
}

/* ---- overview ----
   Built once, lazily, from the slides themselves, so it can never drift out of
   sync with the deck. A card shows what you need to find a slide fast: its
   number, its segment, its target time, and its heading. */
function buildOverview(){
  const grid = document.getElementById('ogrid');
  if(!grid || grid.childElementCount) return;
  slides.forEach((s, k) => {
    const h = s.querySelector('h1, h2, .invariant p');
    const card = document.createElement('button');
    card.className = 'ocard';
    card.innerHTML =
      '<span class="om"><b>' + String(k + 1).padStart(2, '0') + '</b>' +
      '<span>' + (s.dataset.seg || '') + '</span>' +
      '<span>' + (s.dataset.t || '') + '</span></span>' +
      '<span class="ot"></span>';
    card.querySelector('.ot').textContent =
      (h ? h.textContent : '').replace(/\s+/g, ' ').trim().slice(0, 90) || 'Untitled';
    card.addEventListener('click', ev => { ev.stopPropagation(); show(k); toggleOverview(false); });
    grid.appendChild(card);
  });
}
function markOverview(){
  const grid = document.getElementById('ogrid');
  if(!grid) return;
  [...grid.children].forEach((c, k) => c.classList.toggle('here', k === i));
  if(overviewOn && grid.children[i]) grid.children[i].scrollIntoView({block:'nearest'});
}
function toggleOverview(next){
  const ov = document.getElementById('overview');
  if(!ov) return;
  buildOverview();
  overviewOn = next === undefined ? !overviewOn : next;
  ov.classList.toggle('on', overviewOn);
  markOverview();
}

// Sandboxed iframes (about:srcdoc) and some file:// contexts refuse
// history.replaceState with a SecurityError. The deck does not need the URL to
// work, so try once, and if the environment says no, stop asking. Without this
// guard it throws on every single slide change and floods the console.
let hashOk = true;
function syncHash(n){
  if(!hashOk) return;
  try { history.replaceState(null, '', '#' + n); }
  catch(e){ hashOk = false; }
}

// Browser back/forward and manual hash edits both land here.
addEventListener('hashchange', () => {
  if(!hashOk) return;
  const n = parseInt(location.hash.slice(1) || '1') - 1;
  if(n !== i) show(n);
});

function tick(){
  if(!started) return;
  document.body.classList.remove('timer-idle');
  const d = Math.floor((Date.now() - started) / 1000);
  document.getElementById('clock').textContent =
    String(Math.floor(d / 60)).padStart(2, '0') + ':' + String(d % 60).padStart(2, '0');
}
setInterval(tick, 500);

function showJump(){
  const j = document.getElementById('jump');
  if(!j) return;
  j.textContent = jumpBuf;
  j.classList.toggle('on', jumpBuf.length > 0);
}

addEventListener('keydown', e => {
  // Type a slide number, press enter. Faster than arrowing when someone in the
  // room asks you to go back to "the architecture one".
  if(/^[0-9]$/.test(e.key)){ jumpBuf += e.key; showJump(); e.preventDefault(); return; }
  if(e.key === 'Enter' && jumpBuf){ show(parseInt(jumpBuf) - 1); jumpBuf = ''; showJump(); toggleOverview(false); e.preventDefault(); return; }
  if(jumpBuf && (e.key === 'Escape' || e.key === 'Backspace')){ jumpBuf = ''; showJump(); e.preventDefault(); return; }

  if(e.key === 'g'){ toggleOverview(); e.preventDefault(); return; }
  if(e.key === 'Escape'){ toggleOverview(false); e.preventDefault(); return; }

  if(['ArrowRight','ArrowDown',' ','PageDown'].includes(e.key)) { show(i + 1); e.preventDefault(); }
  else if(['ArrowLeft','ArrowUp','PageUp','Backspace','p'].includes(e.key)) { show(i - 1); e.preventDefault(); }
  else if(e.key === 'Home') { show(0); e.preventDefault(); }
  else if(e.key === 'End') { show(slides.length - 1); e.preventDefault(); }
  else if(e.key === 'n'){ notesOn = !notesOn; document.getElementById('notes').classList.toggle('on', notesOn); }
  else if(e.key === 't'){
    started = started ? null : Date.now();
    document.body.classList.toggle('timer-idle', !started);
    if(!started) document.getElementById('clock').textContent = '00:00';
  }
  else if(e.key === 'b'){ document.body.classList.toggle('egress-blocked'); }
});
// Left quarter of the screen goes back, the rest advances. Shift-click also
// goes back, for presenters who click near the middle.
addEventListener('click', e => {
  if(e.target.closest('#notes') || e.target.closest('#overview') || overviewOn) return;
  const back = e.shiftKey || e.clientX < window.innerWidth * 0.25;
  show(back ? i - 1 : i + 1);
});
addEventListener('contextmenu', e => { e.preventDefault(); if(!overviewOn) show(i - 1); });
addEventListener('resize', () => show(i));
let start = 1;
try { start = parseInt(location.hash.slice(1) || '1') || 1; } catch(e){}
show(start - 1);
