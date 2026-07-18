/**
 * Phase 6 — Inline status changes for help flags
 * Two targets:
 *   - Admin: status-btn with [data-admin][data-hid][data-status]
 *   - Participant: status-btn with [data-slug][data-hid][data-status]
 * Both POST as application/x-www-form-urlencoded to /<path>/status.
 */
(function () {
  function setActive(parent, status) {
    parent.querySelectorAll('.status-btn').forEach(function (b) {
      if (b.dataset.status === status) b.classList.add('active');
      else b.classList.remove('active');
    });
    var pill = parent.querySelector('.status-pill');
    if (pill) {
      pill.className = 'status-pill status-' + status;
      pill.textContent = status.replace('_', ' ');
    }
  }

  function send(payload, url) {
    return fetch(url, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }).then(function (resp) {
      if (!resp.ok) throw new Error('HTTP ' + resp.status);
      return resp;
    });
  }

  document.addEventListener('click', function (ev) {
    var btn = ev.target.closest('.status-btn');
    if (!btn) return;
    ev.preventDefault();
    var status = btn.dataset.status;
    var card = btn.closest('.help-card');
    if (btn.dataset.admin) {
      send(
        { status: status },
        '/admin/' + btn.dataset.admin + '/help/' + btn.dataset.hid + '/status'
      )
        .then(function () { setActive(card, status); })
        .catch(function () { alert('Could not update status.'); });
    } else if (btn.dataset.slug) {
      send(
        { status: status },
        '/w/' + btn.dataset.slug + '/me/help/' + btn.dataset.hid + '/status'
      )
        .then(function () { setActive(card, status); })
        .catch(function () { alert('Could not update status.'); });
    }
  });
})();