/* Bar Finder: filter page. Plain JavaScript, no libraries.
   Data is embedded in the page as JSON (see build_site.py), so the page also works when opened from disk. */
(function () {
  'use strict';

  var dataEl = document.getElementById('bar-data');
  if (!dataEl) return;
  var DATA = JSON.parse(dataEl.textContent);
  var BARS = DATA.bars;

  // ---------- filter definitions ----------
  var NUM = {
    minProtein:  { f: 'protein', ge: true,  text: function (v) { return 'Protein ' + v + 'g or more'; } },
    maxCal:      { f: 'cal',     ge: false, text: function (v) { return v + ' calories or fewer'; } },
    maxAdded:    { f: 'added',   ge: false, text: function (v) { return v === 0 ? 'No added sugar' : 'Added sugar ' + v + 'g or less'; } },
    maxBarPrice: { f: 'perBar',  ge: false, text: function (v) { return money(v) + ' or less per bar'; } },
    maxPer20:    { f: 'per20',   ge: false, text: function (v) { return money(v) + ' or less per 20g protein'; } },
    minFiber:    { f: 'fiber',   ge: true,  text: function (v) { return 'Fiber ' + v + 'g or more'; } },
    maxCarbs:    { f: 'carbs',   ge: false, text: function (v) { return 'Carbs ' + v + 'g or less'; } },
    maxFat:      { f: 'fat',     ge: false, text: function (v) { return 'Fat ' + v + 'g or less'; } },
    maxSodium:   { f: 'sodium',  ge: false, text: function (v) { return 'Sodium ' + v + 'mg or less'; } }
  };
  var EXCL = {
    artificial: 'No artificial sweeteners', sugar_alcohol: 'No sugar alcohols', stevia: 'No stevia',
    monk: 'No monk fruit', allulose: 'No allulose', peanut: 'No peanuts', tree_nuts: 'No tree nuts',
    soy: 'No soy', egg: 'No egg', seed_oil: 'No seed oils'
  };
  var MUST = {
    organic: 'USDA Organic', nongmo: 'Non-GMO Project Verified', gf: 'Labeled gluten-free',
    nodairy: 'No dairy ingredients', vegan: 'Vegan by ingredients', draft: 'Not yet checked'
  };
  var PRESETS = {
    protein:    { minProtein: 20 },
    sugar:      { maxAdded: 5 },
    cal:        { maxCal: 200 },
    organic:    { must: ['organic'] },
    artificial: { exclude: ['artificial'] },
    sa:         { exclude: ['sugar_alcohol'] }
  };
  var SORTS = {
    protein: function (a, b) { return b.protein - a.protein; },
    per20:   function (a, b) { return nullLast(a.per20, b.per20); },
    perBar:  function (a, b) { return nullLast(a.perBar, b.perBar); },
    cal:     function (a, b) { return a.cal - b.cal; },
    added:   function (a, b) { return nullLast(a.added, b.added); },
    ratio:   function (a, b) { return (b.protein / b.cal) - (a.protein / a.cal); },
    fiber:   function (a, b) { return b.fiber - a.fiber; }
  };

  var mq = window.matchMedia('(min-width: 900px)');
  var PAGE = 20, shown = PAGE;
  var layoutPref = null, groupBrand = false;   // layoutPref null = automatic: rows on phones, cards on wide screens
  var brandKey = null;                         // set when one brand is open
  function layout() { return layoutPref || 'brands'; }
  function flavLayout() { return (layoutPref === 'rows' || layoutPref === 'cards') ? layoutPref : (mq.matches ? 'cards' : 'rows'); }
  var state, sortKey;
  function emptyState() {
    var s = { exclude: [], must: [] };
    Object.keys(NUM).forEach(function (k) { s[k] = null; });
    return s;
  }
  state = emptyState();
  sortKey = 'protein';

  // ---------- helpers ----------
  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function num(x) { return x == null ? '?' : String(Math.round(x * 10) / 10); }
  function money(x) { return '$' + x.toFixed(2); }
  function nullLast(a, b) {
    if (a == null && b == null) return 0;
    if (a == null) return 1;
    if (b == null) return -1;
    return a - b;
  }
  function $(sel, root) { return (root || document).querySelector(sel); }
  function $$(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }

  function mustOk(b, k) {
    switch (k) {
      case 'organic': return b.claims.organic === true;
      case 'nongmo': return b.claims.nongmo === true;
      case 'gf': return b.claims.gf === true;
      case 'nodairy': return b.noDairy === true;
      case 'vegan': return b.vegan === true;
      case 'draft': return b.draft === true;
    }
    return false;
  }

  // skip = {t: 'n'|'e'|'m', k: key} lets us ask "what if this one filter were removed?"
  function matches(b, st, skip) {
    var k, i, d, val;
    for (k in NUM) {
      if (st[k] == null) continue;
      if (skip && skip.t === 'n' && skip.k === k) continue;
      d = NUM[k]; val = b[d.f];
      if (val == null) return false;
      if (d.ge ? val < st[k] : val > st[k]) return false;
    }
    for (i = 0; i < st.exclude.length; i++) {
      if (skip && skip.t === 'e' && skip.k === st.exclude[i]) continue;
      if (b.has[st.exclude[i]]) return false;
    }
    for (i = 0; i < st.must.length; i++) {
      if (skip && skip.t === 'm' && skip.k === st.must[i]) continue;
      if (!mustOk(b, st.must[i])) return false;
    }
    return true;
  }

  function activeItems() {
    var items = [];
    Object.keys(NUM).forEach(function (k) {
      if (state[k] != null) items.push({ t: 'n', k: k, label: NUM[k].text(state[k]) });
    });
    state.exclude.forEach(function (k) { items.push({ t: 'e', k: k, label: EXCL[k] }); });
    state.must.forEach(function (k) { items.push({ t: 'm', k: k, label: MUST[k] }); });
    return items;
  }

  function removeItem(it) {
    if (it.t === 'n') state[it.k] = null;
    if (it.t === 'e') state.exclude = state.exclude.filter(function (x) { return x !== it.k; });
    if (it.t === 'm') state.must = state.must.filter(function (x) { return x !== it.k; });
  }

  // ---------- rendering ----------
  function card(b) {
    var hit = function (key) { return state[key] != null ? ' hit' : ''; };
    var p = b.best;
    var seals = [];
    if (b.claims.organic === true) seals.push('USDA Organic');
    if (b.claims.nongmo === true) seals.push('Non-GMO Project Verified');
    if (b.claims.gf === true) seals.push('Labeled gluten-free');
    if (b.noDairy === true) seals.push('No dairy ingredients');
    if (b.vegan === true) seals.push('Vegan by ingredients');
    var tags = b.draft ? '<li class="tag flag">Not yet checked</li>' : '';
    tags += b.avail !== 'regular' ? '<li class="tag plain">' + (b.avail === 'seasonal' ? 'Seasonal' : 'Limited run') + '</li>' : '';
    tags += seals.map(function (t) { return '<li class="tag seal">' + esc(t) + '</li>'; }).join('');
    tags += b.sweet.map(function (t) { return '<li class="tag flag">' + esc(t) + '</li>'; }).join('');
    if (b.allergenNames.length) tags += '<li class="tag plain">Contains ' + esc(b.allergenNames.join(', ')) + '</li>';

    var price = '';
    if (p) {
      price = '<div class="price"><div><b class="' + (state.maxBarPrice != null ? 'hit' : '') + '">' + money(p.perBar) + '</b> <span>per bar</span></div>' +
        '<span class="' + (state.maxPer20 != null ? 'hit' : '') + '">' + money(p.per20) + ' per 20g protein</span>' +
        '<span class="pack">Best price: ' + p.packBars + '-bar pack</span>' +
        (p.inStock ? '' : '<span class="oos">Out of stock when checked</span>') + '</div>';
    }
    return '<li><article class="card">' +
      '<div class="who"><span class="mono" style="background:hsl(' + b.hue + ',48%,34%)" aria-hidden="true">' + esc(b.mono) + '</span>' +
      '<div><div class="brand">' + esc(b.gname) + '</div>' +
      '<h3 class="flavor"><a href="' + (DATA.preview ? '#view=' + esc(b.id) : 'bars/' + esc(b.id) + '.html') + '">' + esc(b.flavor) + '</a></h3></div></div>' +
      '<div class="macros">' +
      '<div class="m' + hit('minProtein') + '"><b>' + num(b.protein) + '<i>g</i></b><span>protein</span></div>' +
      '<div class="m' + hit('maxCal') + '"><b>' + num(b.cal) + '</b><span>calories</span></div>' +
      '<div class="m' + hit('maxAdded') + '"><b>' + num(b.added) + '<i>g</i></b><span>added sugar</span></div>' +
      '<div class="m' + hit('minFiber') + '"><b>' + num(b.fiber) + '<i>g</i></b><span>fiber</span></div>' +
      '</div>' +
      '<ul class="tags">' + tags + '</ul>' + price +
      '</article></li>';
  }

  function row(b) {
    var hit = function (key) { return state[key] != null ? ' hit' : ''; };
    var p = b.best;
    // Rows show protein, calories and added sugar. Any other number you are filtering or sorting on is added.
    var nums = [
      ['<span class="rn' + hit('minProtein') + '"><b>' + num(b.protein) + 'g</b> protein</span>'],
      ['<span class="rn' + hit('maxCal') + '"><b>' + num(b.cal) + '</b> cal</span>'],
      ['<span class="rn' + hit('maxAdded') + '"><b>' + num(b.added) + 'g</b> added sugar</span>']
    ].map(function (x) { return x[0]; });
    if (state.minFiber != null) nums.push('<span class="rn hit"><b>' + num(b.fiber) + 'g</b> fiber</span>');
    if (state.maxCarbs != null) nums.push('<span class="rn hit"><b>' + num(b.carbs) + 'g</b> carbs</span>');
    if (state.maxFat != null) nums.push('<span class="rn hit"><b>' + num(b.fat) + 'g</b> fat</span>');
    if (state.maxSodium != null) nums.push('<span class="rn hit"><b>' + num(b.sodium) + 'mg</b> sodium</span>');
    if (p && (state.maxPer20 != null || sortKey === 'per20')) {
      nums.push('<span class="rn' + (state.maxPer20 != null ? ' hit' : '') + '"><b>' + money(p.per20) + '</b> per 20g protein</span>');
    }
    var flags = b.sweet.length ? '<div class="rflags">' + esc(b.sweet.join(', ')) + '</div>' : '';
    var price = p ? '<div class="rpr"><b class="' + (state.maxBarPrice != null ? 'hit' : '') + '">' + money(p.perBar) + '</b> <span>per bar</span>' +
      (p.inStock ? '' : '<div class="oos">Out of stock</div>') + '</div>' : '';
    return '<li><article class="rowc">' +
      '<span class="mono sm" style="background:hsl(' + b.hue + ',48%,34%)" aria-hidden="true">' + esc(b.mono) + '</span>' +
      '<div class="rmain"><div class="rtop"><h3 class="rname"><span class="rbrand">' + esc(b.gname) + '</span> ' +
      '<a href="' + (DATA.preview ? '#view=' + esc(b.id) : 'bars/' + esc(b.id) + '.html') + '">' + esc(b.flavor) + '</a>' + (b.draft ? ' <span class="seas">Unchecked</span>' : '') + (b.avail !== 'regular' ? ' <span class="seas">' + (b.avail === 'seasonal' ? 'Seasonal' : 'Limited') + '</span>' : '') + '</h3>' + price + '</div>' +
      '<div class="rnums">' + nums.join('') + '</div>' + flags + '</div></article></li>';
  }
  function itemHtml(b) { return flavLayout() === 'rows' ? row(b) : card(b); }

  // ---------- brands ----------
  var GROUPS = [], GBYKEY = {};
  (function () {
    BARS.forEach(function (b) {
      var name = b.gname;
      var key = name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
      var g = GBYKEY[key];
      if (!g) { g = GBYKEY[key] = { key: key, name: name, mono: b.mono, hue: b.hue, bars: [] }; GROUPS.push(g); }
      g.bars.push(b);
      b.gkey = key;
    });
  })();
  function cnt(g, fn) { return g.bars.filter(fn).length; }
  function frac(c, n) { return c === n ? 'all' : c + ' of ' + n; }
  function rng(vals, f) {
    var v = vals.filter(function (x) { return x != null; });
    if (!v.length) return '?';
    var lo = Math.min.apply(null, v), hi = Math.max.apply(null, v);
    return lo === hi ? f(lo) : f(lo) + '\u2013' + f(hi);
  }
  function facts(g) {
    var n = g.bars.length, out = [], any = false;
    [['artificial', 'Artificial sweeteners'], ['sugar_alcohol', 'Sugar alcohols'], ['stevia', 'Stevia'], ['monk', 'Monk fruit'], ['allulose', 'Allulose']].forEach(function (p) {
      var c = cnt(g, function (b) { return b.has[p[0]]; });
      if (c) { any = true; out.push('<li class="tag flag">' + p[1] + ': ' + frac(c, n) + '</li>'); }
    });
    if (!any) out.push('<li class="tag seal">No artificial sweeteners, sugar alcohols, stevia, monk fruit or allulose</li>');
    var dairy = cnt(g, function (b) { return b.noDairy === false; });
    if (dairy) out.push('<li class="tag plain">Dairy ingredients: ' + frac(dairy, n) + '</li>');
    [['peanut', 'Peanuts'], ['tree_nuts', 'Tree nuts'], ['soy', 'Soy'], ['egg', 'Egg']].forEach(function (p) {
      var c = cnt(g, function (b) { return b.has[p[0]]; });
      if (c) out.push('<li class="tag plain">' + p[1] + ': ' + frac(c, n) + '</li>');
    });
    [['organic', 'USDA Organic', function (b) { return b.claims.organic === true; }],
     ['nongmo', 'Non-GMO Project Verified', function (b) { return b.claims.nongmo === true; }],
     ['gf', 'Labeled gluten-free', function (b) { return b.claims.gf === true; }],
     ['vegan', 'Vegan by ingredients', function (b) { return b.vegan === true; }]].forEach(function (p) {
      var c = cnt(g, p[2]);
      if (c) out.push('<li class="tag seal">' + p[1] + ': ' + frac(c, n) + '</li>');
    });
    var seas = cnt(g, function (b) { return b.avail !== 'regular'; });
    if (seas) out.push('<li class="tag plain">Seasonal or limited: ' + frac(seas, n) + '</li>');
    var dr = cnt(g, function (b) { return b.draft; });
    if (dr) out.push('<li class="tag flag">Not yet checked: ' + frac(dr, n) + '</li>');
    return out.join('');
  }
  function bcard(g, detail) {
    var n = g.bars.length, filtered = activeItems().length > 0;
    var m = g.bars.filter(function (b) { return matches(b, state); }).length;
    var sub = filtered ? '<span class="mt">' + m + ' of ' + n + '</span> ' + (n === 1 ? 'flavor matches' : 'flavors match')
                       : n + (n === 1 ? ' flavor' : ' flavors');
    var name = detail ? esc(g.name) : '<a href="#brand=' + esc(g.key) + '" data-brand="' + esc(g.key) + '">' + esc(g.name) + '</a>';
    var perBar = g.bars.map(function (b) { return b.perBar; });
    return '<li' + (!detail && filtered && m === 0 ? ' class="dim"' : '') + '><article class="bcard">' +
      '<div class="who"><span class="mono" style="background:hsl(' + g.hue + ',48%,34%)" aria-hidden="true">' + esc(g.mono) + '</span>' +
      '<div><h3 class="bname">' + name + '</h3><div class="bsub">' + sub + '</div></div></div>' +
      '<div class="macros three">' +
      '<div class="m"><b>' + rng(g.bars.map(function (b) { return b.protein; }), function (x) { return num(x) + 'g'; }) + '</b><span>protein</span></div>' +
      '<div class="m"><b>' + rng(g.bars.map(function (b) { return b.cal; }), num) + '</b><span>calories</span></div>' +
      '<div class="m"><b>' + rng(g.bars.map(function (b) { return b.added; }), function (x) { return num(x) + 'g'; }) + '</b><span>added sugar</span></div>' +
      '</div><ul class="tags facts">' + facts(g) + '</ul>' +
      '<div class="price"><div><b>' + rng(perBar, money) + '</b> <span>per bar</span></div><span class="pack">across ' + n + (n === 1 ? ' flavor' : ' flavors') + '</span></div>' +
      '</article></li>';
  }
  var FLAGCOLS = [
      ['Artificial', 'artificial sweeteners', function (b) { return b.has.artificial; }, 'avoid'],
      ['Sugar alcohol', 'sugar alcohols', function (b) { return b.has.sugar_alcohol; }, 'avoid'],
      ['Stevia etc.', 'stevia, monk fruit or allulose', function (b) { return b.has.stevia || b.has.monk || b.has.allulose; }, 'avoid'],
      ['Dairy', 'dairy ingredients', function (b) { return b.noDairy === false; }, 'avoid'],
      ['Peanuts', 'peanuts', function (b) { return b.has.peanut; }, 'avoid'],
      ['Tree nuts', 'tree nuts', function (b) { return b.has.tree_nuts; }, 'avoid'],
      ['Soy', 'soy', function (b) { return b.has.soy; }, 'avoid'],
      ['Egg', 'egg', function (b) { return b.has.egg; }, 'avoid'],
      ['Organic', 'USDA Organic', function (b) { return b.claims.organic === true; }, 'have'],
      ['Non-GMO', 'Non-GMO Project Verified', function (b) { return b.claims.nongmo === true; }, 'have'],
      ['Gluten-free', 'labeled gluten-free', function (b) { return b.claims.gf === true; }, 'have'],
      ['Vegan', 'vegan by ingredients', function (b) { return b.vegan === true; }, 'have']
  ];
  // column groups: s = sweeteners, c = contains, l = labels (m = macros is added where the numbers are drawn)
  [ 's', 's', 's', 'c', 'c', 'c', 'c', 'c', 'l', 'l', 'l', 'l' ].forEach(function (g, i) { FLAGCOLS[i].push(g); });
  var colAuto = true;                                   // until the owner picks a tab, show every column if it fits
  function defaultTab() { return mq.matches ? 'ms' : 'm'; }
  var colTab = 'all';
  function tabSet() {
    return mq.matches ? [['ms', 'Macros and sweeteners'], ['cl', 'Allergens and labels'], ['all', 'All columns']]
                      : [['m', 'Macros'], ['s', 'Sweeteners'], ['c', 'Contains'], ['l', 'Labels $'], ['all', 'All']];
  }
  function validTab(x) { return tabSet().some(function (p) { return p[0] === x; }); }
  function coltabs() {
    if (!validTab(colTab)) colTab = defaultTab();
    return '<div class="coltabs" role="group" aria-label="Choose columns">' + tabSet().map(function (x) {
      return '<button type="button" data-tab="' + x[0] + '" aria-pressed="' + (colTab === x[0] ? 'true' : 'false') + '">' + x[1] + '</button>';
    }).join('') + '</div>';
  }
  function setTab(tab) {
    colTab = tab;
    $$('.btable').forEach(function (tb) { tb.className = tb.className.replace(/show-\w+/, 'show-' + tab); });
    $$('.coltabs button').forEach(function (b) { b.setAttribute('aria-pressed', b.getAttribute('data-tab') === tab ? 'true' : 'false'); });
  }
  function fitColumns() {
    if (!colAuto) return;
    var tb = document.querySelector('.btable');
    if (!tb) return;
    setTab('all');
    var sc = tb.parentNode;
    if (sc.scrollWidth > sc.clientWidth + 1) setTab(defaultTab());
  }
  function p100(b) { return b.cal ? b.protein / b.cal * 100 : null; }
  function f1(x) { return (Math.round(x * 10) / 10).toFixed(1); }
  function orderedBrands() {
    var sorter = SORTS[sortKey] || SORTS.protein;
    var rows = GROUPS.map(function (g) {
      var mb = g.bars.filter(function (b) { return matches(b, state); }).sort(sorter);
      return { g: g, m: mb.length, lead: mb[0] };
    });
    rows.sort(function (a, b) {
      if ((a.m > 0) !== (b.m > 0)) return a.m > 0 ? -1 : 1;
      if (a.m > 0 && b.m > 0) { var r = sorter(a.lead, b.lead); if (r) return r; }
      return a.g.name.localeCompare(b.g.name);
    });
    return rows;
  }
  // one table cell: "All", "11/16" or a dash. kind = 'avoid' (things some people want to avoid) or 'have' (labels people look for)
  function tcell(g, fn, kind, label, grp) {
    var n = g.bars.length, c = g.bars.filter(fn).length;
    if (!c) return '<td class="c0 g-' + grp + '" title="' + label + ': none"><span class="sr">none</span><span aria-hidden="true">&ndash;</span></td>';
    var all = c === n;
    return '<td class="' + (all ? 'call' : 'csome') + ' ' + kind + ' g-' + grp + '" title="' + label + ': ' + (all ? 'all ' + n + ' flavors' : c + ' of ' + n + ' flavors') + '">' + (all ? 'All' : c + '/' + n) + '</td>';
  }
  function brandGrid() {
    var filtered = activeItems().length > 0;
    var cols = FLAGCOLS;
    var head = '<thead><tr class="tgroup"><th class="stick"></th><th colspan="4" class="g-m">Per bar</th><th colspan="3" class="g-s">Sweeteners</th><th colspan="5" class="g-c">Contains</th><th colspan="4" class="g-l">Labels</th><th class="g-p"></th></tr>' +
      '<tr><th class="stick" scope="col">Brand</th><th scope="col" class="g-m">Protein</th><th scope="col" class="g-m">Calories</th><th scope="col" class="g-m" title="Grams of protein for every 100 calories. Higher means more protein for the calories.">Protein per 100 cal</th><th scope="col" class="g-m">Carbs</th>' +
      cols.map(function (c) { return '<th scope="col" class="g-' + c[4] + '" title="' + c[1] + '">' + c[0] + '</th>'; }).join('') + '<th scope="col" class="g-p">Price</th></tr></thead>';
    var body = orderedBrands().map(function (r) {
      var g = r.g, n = g.bars.length;
      var sub = filtered ? '<span class="mt">' + r.m + ' of ' + n + '</span> ' + (n === 1 ? 'flavor matches' : 'flavors match') : n + (n === 1 ? ' flavor' : ' flavors');
      return '<tr data-brand="' + esc(g.key) + '"' + (filtered && r.m === 0 ? ' class="dim"' : '') + '>' +
        '<th scope="row" class="stick"><span class="mono sm" style="background:hsl(' + g.hue + ',48%,34%)" aria-hidden="true">' + esc(g.mono) + '</span>' +
        '<div><a href="#brand=' + esc(g.key) + '" data-brand="' + esc(g.key) + '">' + esc(g.name) + '</a><div class="bsub">' + sub + '</div></div></th>' +
        '<td class="num g-m">' + rng(g.bars.map(function (b) { return b.protein; }), function (x) { return num(x) + 'g'; }) + '</td>' +
        '<td class="num g-m">' + rng(g.bars.map(function (b) { return b.cal; }), num) + '</td>' +
        '<td class="num g-m">' + rng(g.bars.map(p100), f1) + '</td>' +
        '<td class="num g-m">' + rng(g.bars.map(function (b) { return b.carbs; }), function (x) { return num(x) + 'g'; }) + '</td>' +
        cols.map(function (c) { return tcell(g, c[2], c[3], c[1], c[4]); }).join('') +
        '<td class="num g-p">' + rng(g.bars.map(function (b) { return b.perBar; }), money) + '</td></tr>';
    }).join('');
    return '<li class="tablewrap">' + coltabs() + '<div class="scroll"><table class="btable show-' + colTab + '">' + head + '<tbody>' + body + '</tbody></table></div>' +
      '<p class="legend"><b>Protein per 100 cal</b> is grams of protein for every 100 calories (higher is leaner). <b>All</b> means every flavor of the brand, <b>11/16</b> means 11 of its 16 flavors, and a dash means none. ' +
      '<span class="k-avoid">Red</span> marks things some people avoid. <span class="k-have">Black</span> marks labels people look for. ' +
      'Tap a brand to see its flavors.</p></li>';
  }
  function flavorLink(b) {
    return DATA.preview ? '#view=' + esc(b.id) : 'bars/' + esc(b.id) + '.html';
  }
  function frow(b, dim) {
    var hit = function (key) { return state[key] != null ? ' hit' : ''; };
    var tag = (b.draft ? ' <span class="seas">Unchecked</span>' : '') +
      (b.avail !== 'regular' ? ' <span class="seas">' + (b.avail === 'seasonal' ? 'Seasonal' : 'Limited') + '</span>' : '');
    var cells = '<th scope="row" class="stick"><a href="' + flavorLink(b) + '">' + esc(b.flavor) + '</a>' + tag + '</th>' +
      '<td class="num g-m' + hit('minProtein') + '">' + num(b.protein) + 'g</td>' +
      '<td class="num g-m' + hit('maxCal') + '">' + num(b.cal) + '</td>' +
      '<td class="num g-m">' + f1(p100(b)) + '</td>' +
      '<td class="num g-m' + hit('maxCarbs') + '">' + num(b.carbs) + 'g</td>' +
      '<td class="num g-m' + hit('minFiber') + '">' + num(b.fiber) + 'g</td>' +
      '<td class="num g-s">' + (b.sa == null ? '<span class="c0">&ndash;</span>' : num(b.sa) + 'g') + '</td>';
    FLAGCOLS.forEach(function (c) {
      cells += c[2](b) ? '<td class="call ' + c[3] + ' g-' + c[4] + '" title="' + c[1] + '">Yes</td>' : '<td class="c0 g-' + c[4] + '" title="' + c[1] + ': no"><span aria-hidden="true">&ndash;</span><span class="sr">no</span></td>';
    });
    cells += '<td class="num g-p' + hit('maxBarPrice') + '">' + (b.perBar == null ? '?' : money(b.perBar)) + (b.best && !b.best.inStock ? '<div class="oos2">out of stock</div>' : '') + '</td>';
    return '<tr data-bar="' + esc(b.id) + '"' + (dim ? ' class="dim"' : '') + '>' + cells + '</tr>';
  }
  function brandDetail(g) {
    var sorter = SORTS[sortKey] || SORTS.protein;
    var mb = g.bars.filter(function (b) { return matches(b, state); }).sort(sorter);
    var rest = g.bars.filter(function (b) { return !matches(b, state); }).sort(sorter);
    var ncols = 7 + FLAGCOLS.length;
    var head = '<thead><tr class="tgroup"><th class="stick"></th><th colspan="5" class="g-m">Macros</th><th colspan="4" class="g-s">Sweeteners</th><th colspan="5" class="g-c">Contains</th><th colspan="4" class="g-l">Labels</th><th class="g-p"></th></tr>' +
      '<tr><th class="stick" scope="col">Flavor</th><th scope="col" class="g-m">Protein</th><th scope="col" class="g-m">Calories</th><th scope="col" class="g-m" title="Grams of protein for every 100 calories. Higher means more protein for the calories.">Protein per 100 cal</th><th scope="col" class="g-m">Carbs</th><th scope="col" class="g-m">Fiber</th><th scope="col" class="g-s">Sugar alcohol (g)</th>' +
      FLAGCOLS.map(function (c) { return '<th scope="col" class="g-' + c[4] + '" title="' + c[1] + '">' + c[0] + '</th>'; }).join('') +
      '<th scope="col" class="g-p">Price</th></tr></thead>';
    var body = mb.map(function (b) { return frow(b, false); }).join('');
    if (rest.length && activeItems().length) {
      body += '<tr class="divider"><td colspan="' + (1 + ncols) + '">Don\u2019t match your filters (' + rest.length + ')</td></tr>' + rest.map(function (b) { return frow(b, true); }).join('');
    } else {
      body += rest.map(function (b) { return frow(b, false); }).join('');
    }
    var n = g.bars.length;
    return '<li class="bback"><button type="button" id="back-brands">&larr; All brands</button></li>' +
      '<li class="bhead2"><h2>' + esc(g.name) + '</h2><p>' + n + (n === 1 ? ' flavor' : ' flavors') + '. Tap a flavor for its full page.</p></li>' +
      '<li class="tablewrap">' + coltabs() + '<div class="scroll"><table class="btable ftable show-' + colTab + '">' + head + '<tbody>' + body + '</tbody></table></div>' +
      '<p class="legend"><b>Yes</b> means this flavor has it, and a dash means it doesn\u2019t. <span class="k-avoid">Red</span> marks things some people avoid. <span class="k-have">Black</span> marks labels people look for. Yellow shows the numbers your filters are about. <b>Protein per 100 cal</b> is grams of protein for every 100 calories (higher is leaner).</p></li>';
  }

  function scrollToResults() {
    var r = document.getElementById('results');
    if (r && !mq.matches) r.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
  var listEl = $('#list');
  var countEl = $('#count');
  var dockCount = $('#dock-count');
  var activeEl = $('#active');
  var liveEl = $('#live');
  var filterBadge = $('#filter-badge');
  var showBtn = $('#show');

  function render() {
    var items = activeItems();
    var res = BARS.filter(function (b) { return matches(b, state); });
    var sorter = SORTS[sortKey] || SORTS.protein;
    res.sort(function (a, b) {
      var r = sorter(a, b);
      return r !== 0 ? r : (a.brand + a.flavor).localeCompare(b.brand + b.flavor);
    });

    var n = res.length;
    var word = n === 1 ? 'bar' : 'bars';
    var lay = layout();
    var cur = (lay === 'brands' && brandKey && GBYKEY[brandKey]) ? GBYKEY[brandKey] : null;
    if (lay === 'brands' && brandKey && !cur) brandKey = null;
    var bm = GROUPS.filter(function (g) { return g.bars.some(function (b) { return matches(b, state); }); }).length;
    if (lay === 'brands' && !cur) {
      countEl.innerHTML = '<mark>' + bm + '</mark> ' + (bm === 1 ? 'brand' : 'brands') + '<small class="subcount">' + n + ' ' + word + ' match</small>';
      dockCount.innerHTML = '<mark>' + bm + '</mark> ' + (bm === 1 ? 'brand' : 'brands');
      showBtn.textContent = 'Show ' + bm + (bm === 1 ? ' brand' : ' brands');
    } else if (cur) {
      var cm = res.filter(function (b) { return b.gkey === cur.key; }).length;
      countEl.innerHTML = '<mark>' + cm + '</mark> of ' + cur.bars.length + ' flavors match';
      dockCount.innerHTML = '<mark>' + cm + '</mark> of ' + cur.bars.length;
      showBtn.textContent = 'Show ' + cm + ' of ' + cur.bars.length;
    } else {
      countEl.innerHTML = '<mark>' + n + '</mark> ' + word;
      dockCount.innerHTML = '<mark>' + n + '</mark> ' + word;
      showBtn.textContent = 'Show ' + n + ' ' + word;
    }
    $('#group').parentNode.hidden = (lay === 'brands');

    filterBadge.textContent = items.length ? '(' + items.length + ')' : '';
    liveEl.textContent = n + ' ' + word + ' match your filters.';

    activeEl.innerHTML = items.map(function (it, i) {
      return '<button type="button" data-i="' + i + '" aria-label="Remove filter: ' + esc(it.label) + '">' + esc(it.label) + '</button>';
    }).join('');
    $$('button', activeEl).forEach(function (btn) {
      btn.addEventListener('click', function () {
        removeItem(items[+btn.getAttribute('data-i')]);
        update();
      });
    });

    if (n && lay === 'brands') {
      listEl.className = 'list brands tableview' + (cur ? ' open' : '');
      listEl.innerHTML = cur ? brandDetail(cur) : brandGrid();
    } else if (n) {
      listEl.className = 'list ' + (flavLayout() === 'rows' ? 'rows' : 'cards') + (groupBrand ? ' grouped' : '');
      var html = '', remaining = 0;
      if (groupBrand) {
        var groups = [], at = {}, count = 0, gi = 0;
        res.forEach(function (b) {
          if (!(b.brand in at)) { at[b.brand] = groups.length; groups.push({ brand: b.brand, bars: [] }); }
          groups[at[b.brand]].bars.push(b);
        });
        while (gi < groups.length && count < shown) {
          var g = groups[gi++];
          html += '<li class="ghead"><h3>' + esc(g.brand) + '<small>' + g.bars.length + (g.bars.length === 1 ? ' bar' : ' bars') + '</small></h3></li>' +
            g.bars.map(itemHtml).join('');
          count += g.bars.length;
        }
        remaining = n - count;
      } else {
        var slice = res.slice(0, shown);
        html = slice.map(itemHtml).join('');
        remaining = n - slice.length;
      }
      if (remaining > 0) {
        html += '<li class="more-li"><button type="button" id="more">Show ' + Math.min(PAGE, remaining) + ' more (' + remaining + ' left)</button></li>';
      }
      listEl.innerHTML = html;
    } else {
      listEl.className = 'list cards';
      var sug = items.map(function (it) {
        var c = BARS.filter(function (b) { return matches(b, state, it); }).length;
        return { it: it, c: c };
      }).filter(function (s) { return s.c > 0; }).sort(function (a, b) { return b.c - a.c; }).slice(0, 3);
      listEl.innerHTML = '<li class="empty"><h3>No bars match all ' + items.length + ' filters</h3>' +
        '<p>Take one off to see more bars.</p>' +
        (sug.length ? '<ul>' + sug.map(function (s, i) {
          return '<li><button type="button" data-s="' + i + '">Remove &ldquo;' + esc(s.it.label) + '&rdquo; to see ' + s.c + (s.c === 1 ? ' bar' : ' bars') + '</button></li>';
        }).join('') + '</ul>' : '') + '</li>';
      $$('button[data-s]', listEl).forEach(function (btn) {
        btn.addEventListener('click', function () {
          removeItem(sug[+btn.getAttribute('data-s')].it);
          update();
        });
      });
    }
    syncControls();
    if (lay === 'brands') fitColumns();
  }

  function presetOn(def) {
    var ok = true;
    Object.keys(def).forEach(function (k) {
      if (k === 'exclude' || k === 'must') {
        def[k].forEach(function (v) { if (state[k].indexOf(v) < 0) ok = false; });
      } else if (state[k] !== def[k]) ok = false;
    });
    return ok;
  }

  function syncControls() {
    $$('.step').forEach(function (b) {
      var k = b.getAttribute('data-key'), v = parseFloat(b.getAttribute('data-value'));
      b.setAttribute('aria-pressed', state[k] === v ? 'true' : 'false');
    });
    $$('input[data-ex]').forEach(function (i) { i.checked = state.exclude.indexOf(i.getAttribute('data-ex')) >= 0; });
    $$('input[data-must]').forEach(function (i) { i.checked = state.must.indexOf(i.getAttribute('data-must')) >= 0; });
    $$('.chip[data-preset]').forEach(function (b) {
      b.setAttribute('aria-pressed', presetOn(PRESETS[b.getAttribute('data-preset')]) ? 'true' : 'false');
    });
    $('#sort').value = sortKey;
    $$('[data-layout]').forEach(function (b) { b.setAttribute('aria-pressed', layout() === b.getAttribute('data-layout') ? 'true' : 'false'); });
    $('#group').checked = groupBrand;
  }

  // ---------- URL hash (makes a filtered view shareable) ----------
  function toHash() {
    var p = [];
    Object.keys(NUM).forEach(function (k) { if (state[k] != null) p.push(k + '=' + state[k]); });
    if (state.exclude.length) p.push('ex=' + state.exclude.join(','));
    if (state.must.length) p.push('must=' + state.must.join(','));
    if (sortKey !== 'protein') p.push('sort=' + sortKey);
    if (layoutPref) p.push('layout=' + layoutPref);
    if (brandKey) p.push('brand=' + brandKey);
    if (groupBrand) p.push('group=1');
    return p.join('&');
  }
  function fromHash() {
    var h = location.hash.replace(/^#/, '');
    state = emptyState(); sortKey = 'protein'; layoutPref = null; groupBrand = false; brandKey = null;
    if (!h) return;
    h.split('&').forEach(function (part) {
      var kv = part.split('='), k = kv[0], v = kv[1] || '';
      if (NUM[k] && v !== '' && !isNaN(parseFloat(v))) state[k] = parseFloat(v);
      else if (k === 'ex') state.exclude = v.split(',').filter(function (x) { return EXCL[x]; });
      else if (k === 'must') state.must = v.split(',').filter(function (x) { return MUST[x]; });
      else if (k === 'sort' && SORTS[v]) sortKey = v;
      else if (k === 'layout' && (v === 'rows' || v === 'cards' || v === 'brands')) layoutPref = v;
      else if (k === 'brand' && GBYKEY[v]) brandKey = v;
      else if (k === 'group' && v === '1') groupBrand = true;
    });
  }
  function update() {
    shown = PAGE;
    var h = toHash();
    try { if (('#' + h) !== location.hash && (h || location.hash)) location.replace('#' + h); } catch (e) { /* ignore */ }
    render();
  }

  // ---------- events ----------
  $$('.step').forEach(function (b) {
    b.addEventListener('click', function () {
      var k = b.getAttribute('data-key'), v = parseFloat(b.getAttribute('data-value'));
      state[k] = state[k] === v ? null : v;
      update();
    });
  });
  $$('input[data-ex]').forEach(function (i) {
    i.addEventListener('change', function () {
      var k = i.getAttribute('data-ex');
      state.exclude = state.exclude.filter(function (x) { return x !== k; });
      if (i.checked) state.exclude.push(k);
      update();
    });
  });
  $$('input[data-must]').forEach(function (i) {
    i.addEventListener('change', function () {
      var k = i.getAttribute('data-must');
      state.must = state.must.filter(function (x) { return x !== k; });
      if (i.checked) state.must.push(k);
      update();
    });
  });
  $$('.chip[data-preset]').forEach(function (b) {
    b.addEventListener('click', function () {
      var def = PRESETS[b.getAttribute('data-preset')];
      var on = presetOn(def);
      Object.keys(def).forEach(function (k) {
        if (k === 'exclude' || k === 'must') {
          def[k].forEach(function (v) {
            state[k] = state[k].filter(function (x) { return x !== v; });
            if (!on) state[k].push(v);
          });
        } else {
          state[k] = on ? null : def[k];
        }
      });
      update();
    });
  });
  $('#sort').addEventListener('change', function (e) { sortKey = e.target.value; update(); });
  $('#clear').addEventListener('click', function () { state = emptyState(); update(); });
  $$('[data-layout]').forEach(function (b) {
    b.addEventListener('click', function () { layoutPref = b.getAttribute('data-layout'); brandKey = null; update(); });
  });
  $('#group').addEventListener('change', function (e) { groupBrand = e.target.checked; update(); });
  listEl.addEventListener('click', function (e) {
    if (e.target && e.target.id === 'more') { shown += PAGE; render(); }
    if (e.target && e.target.id === 'back-brands') { brandKey = null; update(); scrollToResults(); }
    var tb = e.target.closest && e.target.closest('[data-tab]');
    if (tb) { colAuto = false; setTab(tb.getAttribute('data-tab')); return; }
    var fr = e.target.closest && e.target.closest('tr[data-bar]');
    if (fr && !(e.target.closest && e.target.closest('a'))) { var fa = fr.querySelector('a'); if (fa) fa.click(); return; }
    var tr = e.target.closest && e.target.closest('tr[data-brand]');
    if (tr && !(e.target.closest && e.target.closest('a'))) { brandKey = tr.getAttribute('data-brand'); update(); scrollToResults(); return; }
    var a = e.target.closest && e.target.closest('a[data-brand]');
    if (a) { e.preventDefault(); brandKey = a.getAttribute('data-brand'); update(); scrollToResults(); }
  });
  function onSizeClass() { colAuto = true; colTab = 'all'; render(); }
  if (mq.addEventListener) mq.addEventListener('change', onSizeClass); else if (mq.addListener) mq.addListener(onSizeClass);

  // ---------- mobile sheet ----------
  var panel = $('#filters');
  var lastFocus = null;
  function openSheet() {
    if (mq.matches) return;
    lastFocus = document.activeElement;
    document.body.classList.add('sheet-open');
    panel.setAttribute('role', 'dialog');
    panel.setAttribute('aria-modal', 'true');
    var first = $('button, input', panel);
    if (first) first.focus();
  }
  function closeSheet() {
    document.body.classList.remove('sheet-open');
    panel.removeAttribute('role');
    panel.removeAttribute('aria-modal');
    if (lastFocus && lastFocus.focus) lastFocus.focus();
  }
  $('#open-sheet').addEventListener('click', openSheet);
  $('#close-sheet').addEventListener('click', closeSheet);
  $('#scrim').addEventListener('click', closeSheet);
  showBtn.addEventListener('click', function () {
    closeSheet();
    var r = document.getElementById('results');
    if (r) r.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && document.body.classList.contains('sheet-open')) closeSheet();
  });
  $('#cta').addEventListener('click', function () {
    if (mq.matches) {
      panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
      var first = $('.step', panel);
      if (first) first.focus({ preventScroll: true });
    } else {
      openSheet();
    }
  });
  window.addEventListener('hashchange', function () { fromHash(); render(); });

  fromHash();
  render();
})();
