/* AP World study cut.
   Everything on the page is rendered from data/apworld.json (the list of
   units) and the unit file it points to. Clips play through the official
   YouTube IFrame API on youtube-nocookie.com, using each segment's start and
   end times; nothing is downloaded or re-hosted. */
(function () {
  'use strict';

  var DATA = '../data/';
  var $ = function (id) { return document.getElementById(id); };

  /* ---------- small helpers ---------- */
  var store = {
    get: function (k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set: function (k, v) { try { localStorage.setItem(k, v); } catch (e) { /* private mode */ } }
  };

  function pad(n) { return (n < 10 ? '0' : '') + n; }
  function clock(s) {
    s = Math.max(0, Math.round(s));
    var h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), x = s % 60;
    return h ? h + ':' + pad(m) + ':' + pad(x) : m + ':' + pad(x);
  }
  function minutes(s) { return Math.round(s / 60) + ' min'; }
  function plural(n, word) { return n + ' ' + word + (n === 1 ? '' : 's'); }

  function el(tag, attrs) {
    var node = document.createElement(tag);
    if (attrs) {
      for (var k in attrs) {
        if (!Object.prototype.hasOwnProperty.call(attrs, k) || attrs[k] == null) continue;
        if (k === 'text') node.textContent = attrs[k];
        else if (k === 'class') node.className = attrs[k];
        else node.setAttribute(k, attrs[k]);
      }
    }
    for (var i = 2; i < arguments.length; i++) {
      var c = arguments[i];
      if (c == null) continue;
      node.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
    }
    return node;
  }

  function watchUrl(id, t) {
    return 'https://www.youtube.com/watch?v=' + encodeURIComponent(id) + '&t=' + Math.max(0, Math.floor(t)) + 's';
  }

  /* Fold case, accents and curly quotes one character at a time, so the
     folded string lines up index-for-index with the original (used to put
     <mark> around search hits). */
  var QUOTES = { '‘': "'", '’': "'", '“': '"', '”': '"', '–': '-', '—': '-' };
  function fold(str) {
    var out = '';
    for (var i = 0; i < str.length; i++) {
      var c = str[i];
      if (QUOTES[c]) { out += QUOTES[c]; continue; }
      var d = c.normalize ? c.normalize('NFD').replace(/[̀-ͯ]/g, '') : c;
      out += (d.length === 1 ? d : c).toLowerCase();
    }
    return out;
  }

  /* ---------- state ---------- */
  var unit = null;      // the loaded unit JSON
  var slug = '';
  var segs = [];        // every segment, flattened, in play order
  var cur = -1;         // index into segs
  var includeBonus = store.get('apworld:bonus') !== '0';
  var player = null, ready = false, started = false, pendingPlay = false;
  var loadedAt = 0, pollTimer = null, errorTimer = null;
  var done = {};        // segments finished this visit
  var vocab = [];       // rendered vocab items

  /* ============================================================
     BOOT
     ============================================================ */
  function getJSON(url) {
    return fetch(url, { cache: 'no-cache' }).then(function (r) {
      if (!r.ok) throw new Error(url + ' returned ' + r.status);
      return r.json();
    });
  }

  function fail(msg) {
    var box = $('loadError');
    box.textContent = msg;
    box.hidden = false;
    $('unitNote').textContent = '';
  }

  getJSON(DATA + 'apworld.json').then(function (manifest) {
    var units = manifest.units || [];
    var want = new URLSearchParams(location.search).get('unit');
    var pick = units.filter(function (u) { return u.file && u.slug === want; })[0] ||
               units.filter(function (u) { return u.file; })[0];
    renderUnitTabs(units, pick);
    if (!pick) { fail('No units have been added yet.'); return; }
    slug = pick.slug;
    return getJSON(DATA + pick.file).then(renderUnit);
  }).catch(function (err) {
    fail('Could not load the study data (' + err.message + '). ' +
      (location.protocol === 'file:' ? 'Open this page through a web server, not straight from the file.' : 'Try reloading.'));
  });

  function renderUnitTabs(units, pick) {
    var nav = $('units');
    units.forEach(function (u) {
      var text = u.label + ' · ' + u.name;
      if (u.file) {
        nav.appendChild(el('a', {
          class: 'unit', href: '?unit=' + encodeURIComponent(u.slug),
          'aria-current': pick && pick.slug === u.slug ? 'page' : null
        }, text));
      } else {
        nav.appendChild(el('span', { class: 'unit unit--soon' }, text, ' ', el('em', { text: 'coming next' })));
      }
    });
  }

  function renderUnit(d) {
    unit = d;
    document.title = (d.title || 'AP World').replace(/\s+/g, ' ');
    $('unitTitle').textContent = d.unit || d.title || 'AP World';
    $('unitNote').textContent = d.note || '';

    segs = [];
    var core = 0, bonus = 0, terms = 0, coreTopics = 0;
    d.topics.forEach(function (topic, ti) {
      if (!topic.bonus) coreTopics++;
      terms += (topic.vocab || []).length;
      (topic.segments || []).forEach(function (s) {
        var len = s.end - s.start;
        if (topic.bonus) bonus += len; else core += len;
        segs.push({ i: segs.length, topic: topic, ti: ti, s: s, len: len, bonus: !!topic.bonus });
      });
    });

    $('unitStats').textContent = [
      plural(coreTopics, 'topic'),
      plural(segs.length, 'clip'),
      minutes(core) + ' core' + (bonus ? ' + ' + minutes(bonus) + ' bonus' : ''),
      plural(terms, 'vocab term'),
      plural((d.sources || []).length, 'source video')
    ].join(' · ');
    $('bonusLen').textContent = bonus ? '(' + minutes(bonus) + ')' : '';
    if (!bonus) $('bonusToggle').parentNode.hidden = true;

    renderChapters();
    renderVocab();
    renderCredits();
    setupPlayer();
  }

  /* ============================================================
     CHAPTERS
     ============================================================ */
  function renderChapters() {
    var list = $('chapters');
    list.textContent = '';
    unit.topics.forEach(function (topic, ti) {
      var mine = segs.filter(function (x) { return x.ti === ti; });
      if (!mine.length) return;
      var total = mine.reduce(function (a, x) { return a + x.len; }, 0);
      var ol = el('ol', { class: 'ch-segs' });
      mine.forEach(function (x) {
        var btn = el('button', { class: 'seg', type: 'button', 'data-i': x.i },
          el('span', { class: 'seg__i', text: String(x.i + 1) }),
          el('span', { class: 'seg__label' }, x.s.label, el('span', { class: 'seg__chan', text: x.s.channel })),
          el('span', { class: 'seg__len', text: clock(x.len) })
        );
        btn.addEventListener('click', function () { play(x.i); revealPlayer(); });
        x.btn = btn;
        ol.appendChild(el('li', null, btn));
      });
      var li = el('li', { class: 'ch-topic' + (topic.bonus ? ' ch-topic--bonus' : ''), 'data-ti': ti },
        el('div', { class: 'ch-topic__head' },
          el('span', { class: 'ch-topic__n', text: String(topic.n) }),
          el('span', { text: topic.title }),
          el('span', { class: 'ch-topic__len', text: clock(total) })
        ),
        ol
      );
      topic._li = li;
      list.appendChild(li);
    });
    applyBonus();
  }

  function eligible(i) { return includeBonus || !segs[i].bonus; }
  function nextFrom(i) { for (var j = i + 1; j < segs.length; j++) if (eligible(j)) return j; return -1; }
  function prevFrom(i) { for (var j = i - 1; j >= 0; j--) if (eligible(j)) return j; return -1; }

  function applyBonus() {
    $('bonusToggle').checked = includeBonus;
    unit.topics.forEach(function (t) {
      if (t._li) t._li.classList.toggle('is-skipped', !!t.bonus && !includeBonus);
    });
    var n = 0, len = 0;
    segs.forEach(function (x) { if (eligible(x.i)) { n++; len += x.len; } });
    $('chapterCount').textContent = plural(n, 'clip') + ' · ' + clock(len);
    updateButtons();
  }

  $('bonusToggle').addEventListener('change', function (e) {
    includeBonus = e.target.checked;
    store.set('apworld:bonus', includeBonus ? '1' : '0');
    if (unit) applyBonus();
  });

  function highlight() {
    segs.forEach(function (x) {
      if (!x.btn) return;
      x.btn.classList.toggle('is-current', x.i === cur);
      x.btn.classList.toggle('is-done', !!done[x.i]);
      if (x.i === cur) x.btn.setAttribute('aria-current', 'true'); else x.btn.removeAttribute('aria-current');
    });
    // Keep the current clip in view inside the list without scrolling the page.
    var x = segs[cur], list = $('chapters');
    if (!x || !x.btn) return;
    var top = x.btn.offsetTop - list.offsetTop, bottom = top + x.btn.offsetHeight;
    if (top < list.scrollTop + 40 || bottom > list.scrollTop + list.clientHeight - 20) {
      list.scrollTop = Math.max(0, top - list.clientHeight / 3);
    }
  }

  function revealPlayer() {
    var r = $('watch').getBoundingClientRect();
    if (r.top < -40 || r.top > window.innerHeight * 0.5) {
      $('watch').scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }

  /* ============================================================
     PLAYER
     ============================================================ */
  function setupPlayer() {
    if (!segs.length) return;
    var saved = parseInt(store.get('apworld:' + slug + ':clip'), 10);
    cur = saved >= 0 && saved < segs.length && eligible(saved) ? saved : nextFrom(-1);
    if (cur < 0) cur = 0;
    showNow();
    highlight();
    updateButtons();

    window.onYouTubeIframeAPIReady = createPlayer;
    if (window.YT && window.YT.Player) { createPlayer(); return; }
    var tag = document.createElement('script');
    tag.src = 'https://www.youtube.com/iframe_api';
    tag.async = true;
    tag.onerror = ytBlocked;
    document.head.appendChild(tag);
    setTimeout(function () { if (!ready && !(window.YT && window.YT.Player)) ytBlocked(); }, 12000);
  }

  function ytBlocked() {
    if (ready) return;
    frameMessage('YouTube didn’t load. If your network blocks embedded videos, every clip and vocab card still links straight to YouTube at the right second.',
      segs[cur] ? watchUrl(segs[cur].s.video_id, segs[cur].s.start) : null, 'Open this clip on YouTube');
  }

  function createPlayer() {
    if (player) return;
    var x = segs[cur];
    var vars = { start: x.s.start, end: x.s.end, rel: 0, playsinline: 1, modestbranding: 1 };
    if (location.origin && location.origin !== 'null') vars.origin = location.origin;
    player = new YT.Player('player', {
      host: 'https://www.youtube-nocookie.com',
      videoId: x.s.video_id,
      playerVars: vars,
      events: {
        onReady: function () {
          ready = true;
          $('frameMsg').hidden = true;
          if (pendingPlay) { pendingPlay = false; play(cur); }
        },
        onStateChange: onState,
        onError: onError
      }
    });
  }

  function play(i) {
    if (i < 0 || i >= segs.length) return;
    cur = i;
    clearTimeout(errorTimer);
    $('frameMsg').hidden = true;
    store.set('apworld:' + slug + ':clip', String(i));
    showNow();
    highlight();
    updateButtons();
    if (!ready) { pendingPlay = true; return; }
    started = true;
    loadedAt = Date.now();
    var s = segs[i].s;
    player.loadVideoById({ videoId: s.video_id, startSeconds: s.start, endSeconds: s.end });
    startPoll();
  }

  function finishCurrent() {
    done[cur] = true;
    var n = nextFrom(cur);
    if (n >= 0) { play(n); return; }
    stopPoll();
    started = false;
    highlight();
    $('nowMeta').textContent = 'That’s the whole cut. Run the flashcards next, or tap any clip to rewatch it.';
    $('nowBar').style.width = '100%';
    $('playAllBtn').textContent = '↺ Play again';
    cur = nextFrom(-1);
    store.set('apworld:' + slug + ':clip', String(cur));
  }

  function onState(e) {
    var S = YT.PlayerState;
    if (e.data === S.PLAYING) {
      $('playAllBtn').innerHTML = '&#10074;&#10074; Pause';
      startPoll();
    } else if (e.data === S.PAUSED) {
      $('playAllBtn').innerHTML = '&#9654;&#xFE0E; Resume';
    } else if (e.data === S.ENDED && started && Date.now() - loadedAt > 1500) {
      finishCurrent();
    }
  }

  // Backup for the ENDED event, and drives the progress bar. Also catches a
  // scrub past the clip's end in the YouTube controls.
  function startPoll() {
    if (pollTimer) return;
    pollTimer = setInterval(tick, 500);
  }
  function stopPoll() { clearInterval(pollTimer); pollTimer = null; }

  function tick() {
    if (!ready || !started || !segs[cur]) return;
    var s = segs[cur].s, t = 0;
    try { t = player.getCurrentTime() || 0; } catch (e) { return; }
    var len = s.end - s.start;
    var into = Math.min(Math.max(t - s.start, 0), len);
    $('nowBar').style.width = (len ? into / len * 100 : 0) + '%';
    var time = $('nowTime');
    if (time) time.textContent = clock(into) + ' / ' + clock(len);
    var state = player.getPlayerState && player.getPlayerState();
    // The 1.5 s grace stops a stale reading from the previous clip from
    // skipping the one that is still loading.
    var over = (state === YT.PlayerState.PLAYING && t >= s.end - 0.3) || state === YT.PlayerState.ENDED;
    if (over && Date.now() - loadedAt > 1500 && t >= s.start - 1) finishCurrent();
  }

  function onError(e) {
    var x = segs[cur];
    if (!x) return;
    frameMessage('This clip won’t play in the embed (YouTube error ' + e.data + '). Skipping ahead in a few seconds.',
      watchUrl(x.s.video_id, x.s.start), 'Watch it on YouTube instead');
    var at = cur;
    clearTimeout(errorTimer);
    errorTimer = setTimeout(function () { if (cur === at && started) finishCurrent(); }, 6000);
  }

  function frameMessage(text, href, linkText) {
    var box = $('frameMsg');
    box.textContent = '';
    box.appendChild(el('p', { text: text, style: 'margin:0;max-width:44ch' }));
    if (href) box.appendChild(el('a', { href: href, target: '_blank', rel: 'noopener', text: linkText + ' ↗' }));
    box.hidden = false;
  }

  function showNow() {
    var x = segs[cur];
    if (!x) return;
    var topic = x.topic;
    $('nowTopic').textContent = (topic.bonus ? 'Bonus · ' : 'Topic ' + topic.n + ' · ') +
      topic.title.replace(/^Bonus( debate)?:\s*/i, function (m, deb) { return deb ? 'Debate: ' : ''; });
    $('nowLabel').textContent = x.s.label;
    var meta = $('nowMeta');
    meta.textContent = '';
    meta.appendChild(document.createTextNode(x.s.channel + ' · clip ' + (x.i + 1) + ' of ' + segs.length + ' · '));
    meta.appendChild(el('span', { id: 'nowTime', text: '0:00 / ' + clock(x.len) }));
    meta.appendChild(document.createTextNode(' · '));
    meta.appendChild(el('a', { href: watchUrl(x.s.video_id, x.s.start), target: '_blank', rel: 'noopener', text: 'full video ↗', title: x.s.video_title }));
    $('nowBar').style.width = '0%';
  }

  function updateButtons() {
    if (!segs.length) return;
    $('prevBtn').disabled = prevFrom(cur) < 0;
    $('nextBtn').disabled = nextFrom(cur) < 0;
    if (!started) {
      $('playAllBtn').innerHTML = cur === nextFrom(-1) ? '&#9654;&#xFE0E; Play all' : '&#9654;&#xFE0E; Resume at clip ' + (cur + 1);
    }
  }

  $('playAllBtn').addEventListener('click', function () {
    if (!segs.length) return;
    if (!ready) { pendingPlay = true; $('playAllBtn').textContent = 'Loading…'; return; }
    if (!started) { play(eligible(cur) ? cur : nextFrom(-1)); return; }
    var st = player.getPlayerState();
    if (st === YT.PlayerState.PLAYING || st === YT.PlayerState.BUFFERING) player.pauseVideo();
    else player.playVideo();
  });
  $('nextBtn').addEventListener('click', function () { var n = nextFrom(cur); if (n >= 0) play(n); });
  $('prevBtn').addEventListener('click', function () { var p = prevFrom(cur); if (p >= 0) play(p); });

  /* ============================================================
     VOCAB
     ============================================================ */
  function renderVocab() {
    var root = $('vocabList');
    root.textContent = '';
    vocab = [];
    unit.topics.forEach(function (topic, ti) {
      if (!topic.vocab || !topic.vocab.length) return;
      var grid = el('div', { class: 'v-grid' });
      var first = segs.filter(function (x) { return x.ti === ti; })[0];
      var jump = null;
      if (first) {
        jump = el('a', { href: '#watch', text: '▶︎ play this topic' });
        jump.addEventListener('click', function (e) { e.preventDefault(); play(first.i); revealPlayer(); });
      }
      var sec = el('section', { class: 'v-topic' },
        el('h3', { class: 'v-topic__title' }, el('b', { text: String(topic.n) }), topic.title, jump),
        grid
      );
      topic.vocab.forEach(function (v) {
        var termEl = el('h4', { class: 'v-card__term', text: v.term });
        var defEl = el('p', { class: 'v-card__def', text: v.definition });
        var href = v.link || watchUrl(v.video_id, v.t);
        var card = el('article', { class: 'v-card' }, termEl, defEl,
          el('a', { class: 'v-card__watch', href: href, target: '_blank', rel: 'noopener',
                    'aria-label': 'Watch ' + v.term + ' explained at ' + clock(v.t) + ' on YouTube, ' + v.channel },
            '▶︎ Watch at ' + clock(v.t) + ' ', el('span', { text: '· ' + v.channel })));
        grid.appendChild(card);
        vocab.push({
          v: v, topic: topic, card: card, sec: sec, termEl: termEl, defEl: defEl, href: href,
          hay: fold(v.term + ' \n ' + v.definition + ' \n ' + v.channel)
        });
        vocab[vocab.length - 1].loose = loose(vocab[vocab.length - 1].hay);
      });
      root.appendChild(sec);
    });
    root.appendChild(el('p', { class: 'v-empty', id: 'vEmpty', hidden: '' }, 'No terms match that. Try a shorter word.'));
    filterVocab();
  }

  function marked(node, text, words) {
    node.textContent = '';
    if (!words.length) { node.textContent = text; return; }
    var f = fold(text), hits = [];
    words.forEach(function (w) {
      var at = f.indexOf(w);
      while (at > -1) { hits.push([at, at + w.length]); at = f.indexOf(w, at + w.length); }
    });
    if (!hits.length) { node.textContent = text; return; }
    hits.sort(function (a, b) { return a[0] - b[0]; });
    var pos = 0;
    hits.forEach(function (h) {
      if (h[0] < pos) h[0] = pos;
      if (h[1] <= pos) return;
      node.appendChild(document.createTextNode(text.slice(pos, h[0])));
      node.appendChild(el('mark', { text: text.slice(h[0], h[1]) }));
      pos = h[1];
    });
    node.appendChild(document.createTextNode(text.slice(pos)));
  }

  // Apostrophes dropped, so "mita" finds "Mit\u2019a" and "kings" finds "King\u2019s".
  function loose(str) { return str.replace(/'/g, ''); }

  function query() { return fold($('search').value.trim()).split(/\s+/).filter(Boolean); }

  function filterVocab() {
    var words = query(), shown = 0;
    var secs = [];
    vocab.forEach(function (item) {
      var hit = words.every(function (w) { return item.hay.indexOf(w) > -1 || item.loose.indexOf(loose(w)) > -1; });
      item.card.hidden = !hit;
      item.shown = hit;
      if (hit) shown++;
      marked(item.termEl, item.v.term, hit ? words : []);
      marked(item.defEl, item.v.definition, hit ? words : []);
      if (secs.indexOf(item.sec) < 0) secs.push(item.sec);
    });
    secs.forEach(function (sec) {
      sec.hidden = !vocab.some(function (it) { return it.sec === sec && it.shown; });
    });
    $('vEmpty').hidden = shown > 0;
    $('vocabCount').textContent = words.length
      ? shown + ' of ' + plural(vocab.length, 'term') + ' match “' + $('search').value.trim() + '”'
      : plural(vocab.length, 'term') + '. Each one links to the second it’s explained.';
    $('quizBtn').textContent = words.length && shown ? 'Flashcards (' + shown + ')' : 'Flashcards';
  }

  $('search').addEventListener('input', function () { if (unit) filterVocab(); });

  /* ============================================================
     FLASHCARDS
     ============================================================ */
  var quiz = { deck: [], queue: [], known: 0, again: 0, retried: {}, open: false, flipped: false };
  var dlg = $('quiz');

  function shuffle(a) {
    for (var i = a.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1)), t = a[i]; a[i] = a[j]; a[j] = t;
    }
    return a;
  }

  function startQuiz() {
    var pool = vocab.filter(function (it) { return it.shown; });
    if (!pool.length) pool = vocab.slice();
    quiz.deck = pool;
    quiz.queue = pool.slice();
    quiz.known = 0; quiz.again = 0; quiz.retried = {};
    var words = query();
    $('quizTitle').textContent = 'Flashcards' + (words.length && pool.length < vocab.length ? ' · “' + $('search').value.trim() + '”' : '');
    showCard();
  }

  function showCard() {
    var it = quiz.queue[0];
    var finished = !it;
    $('quizDone').hidden = !finished;
    $('quizCard').hidden = finished;
    $('quizGrade').hidden = true;
    $('quizWatch').hidden = true;
    $('shuffleBtn').disabled = finished;
    $('quizPos').textContent = finished ? '' : plural(quiz.queue.length, 'card') + ' left';
    $('quizScore').textContent = 'Knew ' + quiz.known + ' · Again ' + quiz.again;
    if (finished) {
      var tough = Object.keys(quiz.retried).length;
      $('quizDoneText').textContent = 'Done: all ' + plural(quiz.deck.length, 'card') + '. ' +
        (tough ? tough + ' took more than one try.' : 'Every one on the first try.');
      $('restartBtn').focus();
      return;
    }
    quiz.flipped = false;
    $('quizTopic').textContent = it.topic.bonus ? 'Bonus' : 'Topic ' + it.topic.n;
    $('quizTerm').textContent = it.v.term;
    $('quizDef').textContent = it.v.definition;
    $('quizDef').hidden = true;
    $('quizHint').hidden = false;
    $('quizWatch').href = it.href;
    $('quizWatch').textContent = '▶︎ Watch it explained at ' + clock(it.v.t) + ' (' + it.v.channel + ') ↗';
  }

  function flip() {
    if (!quiz.queue.length) return;
    quiz.flipped = !quiz.flipped;
    $('quizDef').hidden = !quiz.flipped;
    $('quizHint').hidden = quiz.flipped;
    $('quizGrade').hidden = !quiz.flipped;
    $('quizWatch').hidden = !quiz.flipped;
  }

  function grade(knew) {
    if (!quiz.flipped || !quiz.queue.length) return;
    var it = quiz.queue.shift();
    if (knew) quiz.known++;
    else { quiz.again++; quiz.retried[it.v.term] = true; quiz.queue.push(it); }
    showCard();
    if (quiz.queue.length) $('quizCard').focus();
  }

  $('quizBtn').addEventListener('click', function () {
    if (!vocab.length) return;
    startQuiz();
    if (dlg.showModal) dlg.showModal(); else dlg.setAttribute('open', '');
    $('quizCard').focus();
  });
  $('quizClose').addEventListener('click', function () { if (dlg.close) dlg.close(); else dlg.removeAttribute('open'); });
  dlg.addEventListener('click', function (e) { if (e.target === dlg && dlg.close) dlg.close(); });
  $('quizCard').addEventListener('click', flip);
  $('gotBtn').addEventListener('click', function () { grade(true); });
  $('againBtn').addEventListener('click', function () { grade(false); });
  $('restartBtn').addEventListener('click', function () { startQuiz(); $('quizCard').focus(); });
  $('shuffleBtn').addEventListener('click', function () {
    shuffle(quiz.queue);
    showCard();
    $('quizCard').focus();
  });
  dlg.addEventListener('keydown', function (e) {
    var onButton = e.target.tagName === 'BUTTON' || e.target.tagName === 'A';
    if (e.key === ' ' && !onButton) { e.preventDefault(); flip(); }
    else if (e.key === 'ArrowRight') { e.preventDefault(); grade(true); }
    else if (e.key === 'ArrowLeft') { e.preventDefault(); grade(false); }
  });

  /* ============================================================
     CREDITS
     ============================================================ */
  function renderCredits() {
    var list = $('creditList');
    list.textContent = '';
    var used = {};
    segs.forEach(function (x) { used[x.s.video_id] = (used[x.s.video_id] || 0) + 1; });
    (unit.sources || []).forEach(function (src) {
      var n = used[src.video_id] || 0;
      var bits = [src.channel];
      if (src.length_s) bits.push(clock(src.length_s) + ' full video');
      if (n) bits.push(plural(n, 'clip') + ' used');
      list.appendChild(el('li', null,
        el('a', { href: src.url || watchUrl(src.video_id, 0), target: '_blank', rel: 'noopener', text: src.title }),
        el('span', { class: 'credits__chan', text: bits.join(' · ') })
      ));
    });
  }
})();
