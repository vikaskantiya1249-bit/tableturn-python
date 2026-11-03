/* TableTurn frontend. Every screen reads the real API. The one hand copy is the rule table (RULES below):
   tests/rules.csv is not shipped in the image, so the rows are copied here and a reference test keeps them equal. */
(function () {
  "use strict";
  var $ = function (id) { return document.getElementById(id); };
  var esc = function (s) { return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); };
  var fmt = function (s) { return esc(s).replace(/`([^`]+)`/g, "<code>$1</code>").replace(/\*\*(.+?)\*\*/g, "<b>$1</b>"); };
  var BRANCH = "Baner";

  /* ---- the wire: every call goes through here; the last raw answer is shown at the bottom ---- */
  function showWire(status, headers, body) {
    var h = ["location"].filter(function (k) { return headers[k]; }).map(function (k) { return k + ": " + headers[k]; }).join("\n");
    $("wire").textContent = "HTTP " + status + (h ? "\n" + h : "") + "\n" + JSON.stringify(body, null, 2);
  }
  async function call(method, path, body) {
    var opts = { method: method, headers: {} };
    if (body !== undefined) { opts.headers["content-type"] = "application/json"; opts.body = JSON.stringify(body); }
    var r = await fetch(path, opts);
    var data = null;
    try { data = await r.json(); } catch (e) { data = null; }
    var headers = { location: r.headers.get("location") };
    showWire(r.status, headers, data);
    return { status: r.status, ok: r.ok, body: data, headers: headers };
  }
  function refusal(p) {
    if (!p) return "<b>No answer</b>";
    var extra = [];
    if (p.max_covers !== undefined) extra.push("largest table seats " + p.max_covers);
    if (p.must_seat_first) extra.push("seat " + p.must_seat_first + " first");
    if (p.errors) extra.push(p.errors.map(function (e) { return e.field + ": " + e.message; }).join("; "));
    return "<b>" + esc(p.title) + "</b><br>" + esc(p.detail) + (extra.length ? "<br>" + esc(extra.join(" · ")) : "") +
      "<br><small class='muted'>" + p.status + " · " + esc(p.type) + "</small>";
  }
  function partyLink(id) { return "<a href='#' class='openparty' data-id='" + esc(id) + "'>" + esc(id) + "</a>"; }

  function show(screen) {
    document.querySelectorAll(".screen").forEach(function (s) { s.classList.toggle("on", s.id === screen); });
    document.querySelectorAll("#nav button").forEach(function (b) { b.classList.toggle("on", b.dataset.screen === screen); });
    var load = { floor: loadFloor, rules: loadRules, api: loadApi, runtime: loadRuntime };
    if (load[screen]) load[screen]();
  }
  $("nav").addEventListener("click", function (e) { var b = e.target.closest("button[data-screen]"); if (b) show(b.dataset.screen); });
  document.addEventListener("click", function (e) {
    var a = e.target.closest("a.openparty"); if (!a) return;
    e.preventDefault(); $("partyform").party_id.value = a.dataset.id; show("party"); loadParty(a.dataset.id);
  });

  /* ---- the floor ---- */
  async function loadFloor() {
    var q = [];
    if ($("fsection").value) q.push("section=" + $("fsection").value);
    if ($("fstate").value) q.push("state=" + $("fstate").value);
    var r = await call("GET", "/branches/" + BRANCH + "/tables" + (q.length ? "?" + q.join("&") : ""));
    if (!r.ok) { $("grid").innerHTML = "<p class='muted'>" + refusal(r.body) + "</p>"; return; }
    $("floorcount").textContent = r.body.tables.length + " shown · " + r.body.free + " free";
    $("grid").innerHTML = r.body.tables.map(function (t) {
      return "<div class='table " + t.state + "' data-no='" + t.no + "' data-state='" + t.state + "' data-party='" + (t.party_id || "") + "' data-seating='" + (t.seating_id || "") + "'><b>" + t.no + "</b>" +
        t.seats + " seats · " + t.section + "<small><br>" + (t.state === "seated" ? t.party_id + " · " + t.seated_minutes + " min" : t.state === "uncleared" ? "left · not cleared" : "free") + "</small></div>";
    }).join("");
  }
  $("fsection").addEventListener("change", loadFloor);
  $("fstate").addEventListener("change", loadFloor);
  $("grid").addEventListener("click", function (e) {
    var t = e.target.closest(".table"); if (!t) return;
    var box = $("tableaction"); box.hidden = false;
    if (t.dataset.state === "free") {
      box.innerHTML = "<b>" + t.dataset.no + "</b> is free. <label>Party <input id='seatparty' placeholder='W001'></label> <button type='button' id='seatnow' class='btn'>Seat them at " + t.dataset.no + "</button><div id='seatout'></div>";
      $("seatnow").addEventListener("click", async function () {
        var r = await call("POST", "/seatings", { party_id: $("seatparty").value.trim(), table: t.dataset.no });
        $("seatout").innerHTML = r.ok ? "<div class='card ok'>Seated " + partyLink(r.body.party_id) + " at " + r.body.table + " — they waited " + r.body.waited_minutes + " min (seating " + r.body.seating_id + ").</div>" : "<div class='card no'>" + refusal(r.body) + "</div>";
        loadFloor();
      });
      return;
    }
    box.innerHTML = "<b>" + t.dataset.no + "</b> — " + partyLink(t.dataset.party) + (t.dataset.state === "seated" ? " is at the table." : " has left; the table is not cleared.") +
      " <label>Seating <input id='actseating' value='" + esc(t.dataset.seating) + "'></label> <button type='button' id='leavebtn' class='btn'>Leave</button> <button type='button' id='clearbtn' class='btn'>Clear</button><div id='actout'></div>";
    async function turn(verb) {
      var r = await call("POST", "/seatings/" + encodeURIComponent($("actseating").value.trim()) + "/" + verb);
      $("actout").innerHTML = r.ok ? "<div class='card ok'>" + (verb === "leave" ? "Left at " + r.body.left_at + " — the table shows uncleared until Joseph clears it." : "Cleared at " + r.body.cleared_at + " — the table was theirs for <b>" + r.body.turn_minutes + " min</b> (seated → left), and it is free again.") + "</div>" : "<div class='card no'>" + refusal(r.body) + "</div>";
      loadFloor();
    }
    $("leavebtn").addEventListener("click", function () { turn("leave"); });
    $("clearbtn").addEventListener("click", function () { turn("clear"); });
  });

  /* ---- waitlist ---- */
  $("joinform").addEventListener("submit", async function (e) {
    e.preventDefault();
    var f = e.target, body = { name: f.name.value, covers: Number(f.covers.value) };
    if (f.phone.value) body.phone = f.phone.value;
    var r = await call("POST", "/waitlist", body);
    $("joinok").hidden = !r.ok; $("joinno").hidden = r.ok;
    if (r.ok) {
      $("joinok").innerHTML = "<b>" + partyLink(r.body.party_id) + "</b> · " + esc(r.body.name) + ", " + r.body.covers + " covers · position <b>" + r.body.position + "</b>" + (r.body.quoted_minutes !== undefined ? " · quoted <b>" + r.body.quoted_minutes + " min</b> at " + r.body.quoted_at : "") + "<br><small class='muted'>Location: " + esc(r.headers.location) + "</small>";
    } else {
      $("joinno").innerHTML = refusal(r.body);
    }
  });

  /* ---- one party ---- */
  var LINE = {
    joined: function (ev) { return "joined · " + ev.covers + " covers"; },
    quoted: function (ev) { return "quoted " + ev.quoted_minutes + " min"; },
    seated: function (ev) { return "seated at " + ev.table + " · waited " + ev.waited_minutes + " min"; },
    left: function () { return "left the table"; },
    cleared: function (ev) { return "table cleared · turn " + ev.turn_minutes + " min"; }
  };
  async function loadParty(id) {
    var r = await call("GET", "/parties/" + encodeURIComponent(id));
    $("partycard").hidden = false;
    if (!r.ok) { $("partycard").innerHTML = refusal(r.body); return; }
    var p = r.body;
    var cleared = (p.events || []).filter(function (ev) { return ev.kind === "cleared"; })[0];
    var numbers = [p.quoted_minutes === undefined ? "quoted —" : "quoted " + p.quoted_minutes + " min", p.waited_minutes === undefined ? "not seated yet" : "waited " + p.waited_minutes + " min"];
    if (cleared) numbers.push("turn " + cleared.turn_minutes + " min");
    $("partycard").innerHTML = "<b>" + p.party_id + "</b> · " + esc(p.name) + " · " + p.covers + " covers · position " + p.position + " · <b>" + p.state + "</b>" + (p.table ? " · table " + p.table : "") +
      "<p><b>" + numbers.join(" · ") + "</b></p>" +
      "<ul class='timeline'>" + (p.events || []).map(function (ev) {
        return "<li><time>" + ev.at + "</time>" + esc((LINE[ev.kind] || function () { return ev.kind; })(ev)) + "</li>";
      }).join("") + "</ul>";
  }
  $("partyform").addEventListener("submit", function (e) { e.preventDefault(); loadParty(e.target.party_id.value.trim()); });

  /* ---- rule book ---- */
  /* rules.csv >>> */
  var RULES = [
    {"case": "fits", "tag": "seat", "setup": "join 6", "action": "seat T20", "status_default": "201", "type_default": "", "status_never": "201", "type_never": "", "status_always": "201", "type_always": "", "given": "a six joins; seat them at T20 (six-top)"},
    {"case": "too_small", "tag": "seat", "setup": "join 6", "action": "seat T11", "status_default": "409", "type_default": "/errors/table-too-small", "status_never": "409", "type_never": "/errors/table-too-small", "status_always": "409", "type_always": "/errors/table-too-small", "given": "a six joins; seat them at T11 (four-top)"},
    {"case": "already_seated", "tag": "seat", "setup": "join 2;seat T01", "action": "seat T02", "status_default": "409", "type_default": "/errors/already-seated", "status_never": "409", "type_never": "/errors/already-seated", "status_always": "409", "type_always": "/errors/already-seated", "given": "a two is seated at T01; seat them again at T02"},
    {"case": "not_cleared", "tag": "seat", "setup": "join 2;seat T01;leave;join 2", "action": "seat T01", "status_default": "409", "type_default": "/errors/table-not-cleared", "status_never": "409", "type_never": "/errors/table-not-cleared", "status_always": "409", "type_always": "/errors/table-not-cleared", "given": "a two seated at T01 leaves; a new two is seated at T01"},
    {"case": "party_too_big", "tag": "join", "setup": "", "action": "join 9", "status_default": "400", "type_default": "/errors/party-too-big", "status_never": "400", "type_never": "/errors/party-too-big", "status_always": "400", "type_always": "/errors/party-too-big", "given": "a party of nine joins"},
    {"case": "malformed", "tag": "join", "setup": "", "action": "join 0", "status_default": "422", "type_default": "/errors/validation", "status_never": "422", "type_never": "/errors/validation", "status_always": "422", "type_always": "/errors/validation", "given": "a party of 0 joins"},
    {"case": "unknown_party", "tag": "seat", "setup": "", "action": "seat W999 T20", "status_default": "404", "type_default": "/errors/no-such-party", "status_never": "404", "type_never": "/errors/no-such-party", "status_always": "404", "type_always": "/errors/no-such-party", "given": "nobody joined as W999; seat W999 at T20"},
    {"case": "unknown_table", "tag": "seat", "setup": "join 2", "action": "seat T99", "status_default": "404", "type_default": "/errors/no-such-table", "status_never": "404", "type_never": "/errors/no-such-table", "status_always": "404", "type_always": "/errors/no-such-table", "given": "a two joins; seat them at T99 (no such table)"},
    {"case": "two_at_four_top_nobody_larger", "tag": "upgrade", "setup": "join 2", "action": "seat T11", "status_default": "201", "type_default": "", "status_never": "409", "type_never": "/errors/overtaking", "status_always": "201", "type_always": "", "given": "a two joins, nobody else waiting; seat them at T11 (four-top)"},
    {"case": "two_at_four_top_four_waiting", "tag": "upgrade", "setup": "join 4;join 2", "action": "seat T11", "status_default": "409", "type_default": "/errors/overtaking", "status_never": "409", "type_never": "/errors/overtaking", "status_always": "201", "type_always": "", "given": "a four joins, then a two; seat the two at T11 (four-top)"}
  ];
  /* <<< rules.csv */
  function expected(row, mode) {
    var type = row["type_" + mode];
    return row["status_" + mode] + (type ? " " + type.replace("/errors/", "") : "");
  }
  function paintRuleTable() {
    var mode = $("ruleupgrade").value;
    $("ruletable").innerHTML = "<tr><th>Case</th><th>Tag</th><th>Given, then</th><th>Expected (" + esc($("ruleupgrade").options[$("ruleupgrade").selectedIndex].text) + ")</th></tr>" + RULES.map(function (r) {
      var moves = !(expected(r, "default") === expected(r, "never") && expected(r, "never") === expected(r, "always"));
      return "<tr" + (moves ? " class='moves'" : "") + "><td><code>" + r["case"] + "</code></td><td>" + r.tag + "</td><td>" + esc(r.given) + "</td><td><code>" + expected(r, mode) + "</code></td></tr>";
    }).join("");
  }
  $("ruleupgrade").addEventListener("change", paintRuleTable);
  var UPGRADE_TEXT = {
    never: "never — a party sits only at a table whose seats equal its covers (so a party of 1, 3 or 5 can join but cannot be seated)",
    when_nobody_larger_waits: "only when no waiting party with more covers could be seated at that table",
    always: "always"
  };
  async function loadRules() {
    var r = await call("GET", "/settings");
    if (r.ok) {
      var s = r.body;
      $("settings").innerHTML = "<dt>Default quote</dt><dd>" + s.default_quote_minutes + " minutes — what every party is told when they join (the real wait is measured at seating) <code>DEFAULT_QUOTE_MINUTES=" + s.default_quote_minutes + "</code></dd>" +
        "<dt>Largest party</dt><dd>" + s.max_covers + " — the biggest table in the branch; more than this is refused as party-too-big</dd>" +
        "<dt>A smaller party may take a larger table</dt><dd>" + esc(UPGRADE_TEXT[s.small_party_upgrade] || s.small_party_upgrade) + " <code>SMALL_PARTY_UPGRADE=" + s.small_party_upgrade + "</code></dd>";
      $("ruleupgrade").value = s.small_party_upgrade === "when_nobody_larger_waits" ? "default" : s.small_party_upgrade;
    }
    paintRuleTable();
    var spec = await (await fetch("/openapi.json")).json();
    var seen = {}, rows = [];
    Object.keys(spec.paths).forEach(function (path) {
      Object.keys(spec.paths[path]).forEach(function (m) {
        var responses = spec.paths[path][m].responses || {};
        Object.keys(responses).forEach(function (status) {
          var content = responses[status].content && responses[status].content["application/problem+json"];
          if (!content || Number(status) >= 500) return;
          var examples = content.examples ? Object.keys(content.examples).map(function (k) { return content.examples[k].value; }) : content.example ? [content.example] : [];
          examples.forEach(function (ex) {
            var key = ex.type + "@" + m.toUpperCase() + " " + path;
            if (seen[key]) return; seen[key] = true;
            rows.push([Number(status), ex.type, ex.title, m.toUpperCase() + " " + path, Object.keys(ex).filter(function (k) { return ["type", "title", "status", "detail"].indexOf(k) < 0; }).join(", ")]);
          });
        });
      });
    });
    rows.sort(function (a, b) { return a[0] - b[0] || a[1].localeCompare(b[1]); });
    $("refusals").innerHTML = "<tr><th>Status</th><th>Type</th><th>Title</th><th>Where</th><th>Extra fields</th></tr>" + rows.map(function (r) { return "<tr><td>" + r[0] + "</td><td><code>" + esc(r[1]) + "</code></td><td>" + esc(r[2]) + "</td><td><code>" + esc(r[3]) + "</code></td><td>" + esc(r[4]) + "</td></tr>"; }).join("");
  }

  /* ---- API ---- */
  var SAMPLES = { "POST /waitlist": { name: "Kulkarni", covers: 6 }, "POST /seatings": { party_id: "W001", table: "T20" } };
  function samplePath(path) { return path.replace("{branch}", BRANCH).replace("{no}", "T11").replace("{party_id}", "W001").replace("{seating_id}", "S001"); }
  async function loadApi() {
    var r = await call("GET", "/openapi.json");
    if (!r.ok) return;
    var rows = [];
    Object.keys(r.body.paths).forEach(function (path) {
      Object.keys(r.body.paths[path]).forEach(function (m) {
        var op = r.body.paths[path][m];
        rows.push("<tr><td><code>" + m.toUpperCase() + " " + esc(path) + "</code></td><td>" + esc(op.summary || "") + "</td><td>" + Object.keys(op.responses).join(" · ") +
          "</td><td><button type='button' class='send' data-m='" + m.toUpperCase() + "' data-p='" + esc(path) + "'>Send</button></td></tr>");
      });
    });
    $("endpoints").innerHTML = "<tr><th>Call</th><th>What it does</th><th>Answers</th><th></th></tr>" + rows.join("");
  }
  $("endpoints").addEventListener("click", function (e) {
    var b = e.target.closest("button.send"); if (!b) return;
    call(b.dataset.m, samplePath(b.dataset.p), SAMPLES[b.dataset.m + " " + b.dataset.p]);
  });

  /* ---- runtime ---- */
  async function loadRuntime() {
    var r = await call("GET", "/healthz");
    $("healthdot").className = "dot " + (r.ok ? "up" : "down");
    $("healthtext").textContent = r.ok ? "up — GET /healthz " + JSON.stringify(r.body) + " (the app answered and reached its database)" : "down — GET /healthz answered " + r.status;
    $("runtimeline").textContent = "image tableturn · built FROM python:3.12-slim";
  }

  /* Restart the container: the list before and after. There is no list endpoint, so every
     party is read one at a time — W001, W002, … until the first id that is not on the list. */
  var SNAPSHOT_KEY = "tableturn.restart.before";
  async function readList() {
    var out = [];
    for (var n = 1; n < 1000; n++) {
      var id = "W" + String(n).padStart(3, "0");
      var r = await fetch("/parties/" + id);
      if (r.status === 404) break;
      if (!r.ok) throw new Error("GET /parties/" + id + " answered " + r.status);
      var p = await r.json();
      out.push({ party_id: p.party_id, state: p.state, quoted_minutes: p.quoted_minutes, quoted_at: p.quoted_at });
    }
    return out;
  }
  function restartOut(html) { $("restartout").hidden = false; $("restartout").innerHTML = html; }
  $("beforebtn").addEventListener("click", async function () {
    try {
      var list = await readList();
      try { localStorage.setItem(SNAPSHOT_KEY, JSON.stringify({ at: new Date().toISOString(), parties: list })); }
      catch (e) { restartOut("<div class='card no'>This browser would not keep the copy (" + esc(e.message) + ").</div>"); return; }
      restartOut("<div class='card ok'>Kept " + list.length + " parties and their quoted minutes. Now run the two commands, reload, and press After restart.</div>");
    } catch (e) { restartOut("<div class='card no'>" + esc(e.message) + "</div>"); }
  });
  $("afterbtn").addEventListener("click", async function () {
    var before = null;
    try { before = JSON.parse(localStorage.getItem(SNAPSHOT_KEY) || "null"); } catch (e) { before = null; }
    if (!before) { restartOut("<div class='card no'>No copy from before the restart — press Before restart first.</div>"); return; }
    var after;
    try { after = await readList(); } catch (e) { restartOut("<div class='card no'>" + esc(e.message) + "</div>"); return; }
    var now = {}, diffs = [];
    after.forEach(function (p) { now[p.party_id] = p; });
    before.parties.forEach(function (p) {
      var q = now[p.party_id];
      if (!q) { diffs.push(p.party_id + " is gone"); return; }
      ["state", "quoted_minutes", "quoted_at"].forEach(function (k) { if (p[k] !== q[k]) diffs.push(p.party_id + " " + k + ": " + p[k] + " → " + q[k]); });
      delete now[p.party_id];
    });
    Object.keys(now).forEach(function (id) { diffs.push(id + " is new since the copy"); });
    restartOut(diffs.length ? "<div class='card no'><b>Changed</b><ul>" + diffs.map(function (d) { return "<li>" + esc(d) + "</li>"; }).join("") + "</ul></div>"
      : "<div class='card ok'><b>unchanged</b> — the same " + before.parties.length + " parties, each with the quoted minutes it had before the restart.</div>");
  });

  /* ---- walkthrough: the tickets, one at a time, on top of the screens they built ---- */
  var WALK = null, step = 0;
  var TAGS = { floor: ["B-01", "B-05"], waitlist: ["B-02", "B-03"], party: ["B-03", "B-06"], rules: ["B-04", "B-08"], api: ["B-07"], runtime: ["B-09", "B-10"] };
  var SCREEN_NAMES = { floor: "The floor", waitlist: "Waitlist", party: "Party", rules: "Rule book", api: "API", runtime: "Runtime" };
  function list(items) { return "<ul>" + items.map(function (s) { return "<li>" + fmt(s) + "</li>"; }).join("") + "</ul>"; }
  function acTable(rows) {
    return "<table class='tbl ac'><tr><th></th><th>given</th><th>when</th><th>then</th></tr>" + rows.map(function (r, i) {
      return "<tr><td>" + (i + 1) + "</td><td>" + fmt(r[0]) + "</td><td>" + fmt(r[1]) + "</td><td>" + fmt(r[2]) + "</td></tr>";
    }).join("") + "</table>";
  }
  function endpoint(e) {
    var h = "<div class='ep'><div class='sig'><b>" + e.m + "</b> " + esc(e.p) + "</div>";
    if (e.q) h += "<div class='muted'>? " + fmt(e.q) + "</div>";
    if (e.req) h += "<div class='muted'>request</div><pre>" + esc(JSON.stringify(e.req, null, 2)) + "</pre>";
    if (e.res) h += "<div class='muted'>response</div><pre>" + esc(JSON.stringify(e.res, null, 2)) + "</pre>";
    if (e.codes.length) h += "<table class='tbl ac'><tr><th>status</th><th>type</th><th>when</th></tr>" + e.codes.map(function (c) {
      return "<tr><td class='st " + (/^2/.test(c[0]) ? "ok" : "no") + "'>" + esc(c[0]) + "</td><td><code>" + esc(c[1]) + "</code></td><td>" + fmt(c[2]) + "</td></tr>";
    }).join("") + "</table>";
    return h + "</div>";
  }
  function paintStep() {
    var s = WALK.steps[step];
    $("walkpos").textContent = "Ticket " + (step + 1) + " of " + WALK.steps.length + " · " + WALK.level;
    $("walkprev").disabled = step === 0; $("walknext").disabled = step === WALK.steps.length - 1;
    $("walkid").textContent = s.id; $("walktitle").textContent = s.title; $("walkscene").innerHTML = fmt(s.scene);
    $("walkus").innerHTML = "As a <b>" + esc(s.story.as) + "</b>, I want to " + fmt(s.story.want) + ", so that " + fmt(s.story.so) + ".";
    $("walktry").innerHTML = "<div class='lbl'>Try it — " + SCREEN_NAMES[s.try.screen] + " screen</div><p>" + fmt(s.try.do) + "</p>" +
      "<div class='lbl'>What will happen</div><p>" + fmt(s.try.see) + "</p><button type='button' id='walkgo'>Go to " + SCREEN_NAMES[s.try.screen] + "</button>";
    $("walkgo").addEventListener("click", function () { show(s.try.screen); document.getElementById(s.try.screen).scrollIntoView({ behavior: "smooth", block: "start" }); });
    $("walkbuild").innerHTML = fmt(s.build); $("walkfollows").innerHTML = fmt(s.follows);
    $("walkcontract").innerHTML = "<p>" + fmt(s.summary) + "</p>" +
      (s.endpoints.length ? s.endpoints.map(endpoint).join("") : "<p class='muted'>No HTTP surface changes on this day — the work is in the code, the database or the container.</p>") +
      "<div class='muted' style='margin-top:8px'>What is stored</div>" + list(s.data) + "<div class='muted' style='margin-top:8px'>Rules the backend enforces</div>" + list(s.rules);
    $("walkacuser").innerHTML = acTable(s.ac_user); $("walkacapi").innerHTML = acTable(s.ac_api); $("walkdone").innerHTML = list(s.done);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }
  async function openWalk(id) {
    if (!WALK) WALK = await (await fetch("/static/walkthrough.json")).json();
    if (id) step = Math.max(0, WALK.steps.findIndex(function (s) { return s.id === id; }));
    $("walk").hidden = false; $("walkbtn").classList.add("on"); paintStep();
  }
  $("walkbtn").addEventListener("click", function () { if ($("walk").hidden) openWalk(); else { $("walk").hidden = true; $("walkbtn").classList.remove("on"); } });
  $("walkclose").addEventListener("click", function () { $("walk").hidden = true; $("walkbtn").classList.remove("on"); });
  $("walkprev").addEventListener("click", function () { if (step > 0) { step--; paintStep(); } });
  $("walknext").addEventListener("click", function () { if (step < WALK.steps.length - 1) { step++; paintStep(); } });
  Object.keys(TAGS).forEach(function (screen) {
    var h2 = document.querySelector("#" + screen + " h2");
    TAGS[screen].forEach(function (id) { h2.insertAdjacentHTML("beforeend", "<span class='tag' data-step='" + id + "' title='Open this ticket in the walkthrough'>" + id + "</span>"); });
  });
  document.addEventListener("click", function (e) { var t = e.target.closest(".tag"); if (t) openWalk(t.dataset.step); });

  show("floor");
})();
