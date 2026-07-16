// Workshop Helmsman — participant-side polling loop.
// Re-fetches /w/<slug>/data every 4 seconds and re-renders
// the leaderboard + help flags. Falls back gracefully on network errors.

(function () {
  var ctx = (typeof window !== "undefined" && window.__helmsman) || {};
  var slug = ctx.slug;
  if (!slug) return;

  var leaderboardEl = document.getElementById("leaderboard-list");
  var helpEl = document.getElementById("help-list");
  var mineBar = document.getElementById("my-bar");
  var mineText = document.getElementById("my-progress-text");
  var minePct = document.getElementById("my-progress-pct");
  var milestonesEl = document.getElementById("milestones-list");

  var POLL_MS = 4000;
  var meId = ctx.meId || null;
  var lastSince = null;

  function fmtTime(iso) {
    try {
      var d = new Date(iso);
      if (isNaN(d.getTime())) return "";
      var hh = String(d.getUTCHours()).padStart(2, "0");
      var mm = String(d.getUTCMinutes()).padStart(2, "0");
      var ss = String(d.getUTCSeconds()).padStart(2, "0");
      return hh + ":" + mm + ":" + ss + " UTC";
    } catch (e) { return ""; }
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, '&')
      .replace(/</g, '<')
      .replace(/>/g, '>')
      .replace(/"/g, '&#34;')
  }

  function renderLeaderboard(rows) {
    if (!leaderboardEl) return;
    if (!rows || !rows.length) {
      leaderboardEl.innerHTML = '<li class="muted">No participants yet.</li>';
      return;
    }
    leaderboardEl.innerHTML = rows.map(function (r) {
      var me = meId && r.id === meId ? ' leaderboard-me' : '';
      var meLabel = meId && r.id === meId ? ' <small>(you)</small>' : '';
      return '<li class="leaderboard-row' + me + '">' +
        '<span class="leaderboard-name">' + escapeHtml(r.name) + meLabel + '</span>' +
        '<span class="leaderboard-progress">' +
          '<span class="bar small"><div class="bar-fill" style="width:' + r.pct + '%"></div></span>' +
          '<small>' + r.completed_count + ' / ' + r.total + '</small>' +
        '</span>' +
      '</li>';
    }).join("");
  }

  function renderHelp(rows) {
    if (!helpEl) return;
    if (!rows || !rows.length) {
      helpEl.innerHTML = '<li class="muted">No help flags yet.</li>';
      return;
    }
    helpEl.innerHTML = rows.map(function (h) {
      return '<li class="help-card">' +
        '<div class="help-meta"><strong>' + escapeHtml(h.participant_name) + '</strong>' +
        '<small class="muted">· ' + escapeHtml(fmtTime(h.created_at)) + '</small></div>' +
        '<div class="help-body">' + escapeHtml(h.message) + '</div>' +
      '</li>';
    }).join("");
  }

  function updateMine(payload, currentCompletedIds) {
    if (mineBar && mineText && minePct) {
      var me = (payload.leaderboard || []).find(function (r) { return meId && r.id === meId; });
      if (me) {
        mineBar.style.width = me.pct + "%";
        mineText.textContent = me.completed_count;
        minePct.textContent = me.pct;
      }
    }
    if (milestonesEl && currentCompletedIds && payload.milestones) {
      // Update chip markers on milestones when the polled data shows new completions
      Array.prototype.forEach.call(milestonesEl.querySelectorAll(".milestone"), function (li) {
        var mid = li.getAttribute("data-mid");
        if (currentCompletedIds[mid]) {
          li.classList.add("milestone-done");
        }
      });
    }
  }

  function pollOnce() {
    var url = "/w/" + encodeURIComponent(slug) + "/data";
    if (lastSince) url += "?since=" + encodeURIComponent(lastSince);
    fetch(url, { credentials: "same-origin" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) {
        if (!j || !j.ok) return;
        lastSince = j.server_time;
        renderLeaderboard(j.leaderboard);
        renderHelp(j.help_requests);
        // We already drew state at SSR — but if completions exist server-side, derive set
        var completedIds = {};
        var me = (j.leaderboard || []).find(function (r) { return meId && r.id === meId; });
        if (me) {
          // we don't have individual milestone IDs from this JSON, but
          // visual progress bar is enough for the live-tick (the buttons
          // do a full reload and SSR the proper state).
          updateMine(j, completedIds);
        }
      })
      .catch(function () { /* swallow — next tick will retry */ });
  }

  // Initial tick fires immediately so the user doesn't see a stale flash,
  // then poll every POLL_MS.
  pollOnce();
  setInterval(pollOnce, POLL_MS);
})();
