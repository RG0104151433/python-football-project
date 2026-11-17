/* Load a sourced morning snapshot without changing any sealed forecast value. */
(() => {
  'use strict';
  const snapshot = window.matchdayResultsSnapshot;
  if (!snapshot) return;
  let retries = 0;
  function install() {
    if (!window.reviewAPI || !window.forecastHoverV5 || document.querySelectorAll('main>.slide').length !== 14) {
      if (++retries < 200) setTimeout(install, 25);
      return;
    }
    const tiles = document.querySelector('#resultTiles');
    const status = document.querySelector('#importStatus');
    const seedKey = 'footballResultsSeedV1';
    const digest = snapshot.csv_sha256;
    const originalForecasts = JSON.stringify(window.reviewAPI.getData().forecasts);
    let seedApplied = false;
    try { seedApplied = localStorage.getItem(seedKey) === digest && !!localStorage.getItem('footballResultsV2'); } catch {}
    function sourceNote(message) {
      status.textContent = message + ' Snapshot checked 17 Nov 2026, 09:19 Beijing: 44 final, 8 pending. Remaining fixtures start 18 Nov, 03:45 Beijing.';
    }
    function decorate() {
      // Results are an existing global lexical binding from the base deck.
      for (const tile of tiles.querySelectorAll('button[data-id]')) {
        const r = results[tile.dataset.id];
        const label = tile.innerHTML.split('<br>')[0];
        const f = window.reviewAPI.getData().forecasts.find(x => x.id === tile.dataset.id);
        if (r?.status === 'final') {
          tile.innerHTML = label + '<br><strong>' + r.home_score + '–' + r.away_score + '</strong> · ' + window.reviewAPI.judge(f);
          tile.setAttribute('title', f.home + ' ' + r.home_score + '–' + r.away_score + ' ' + f.away + ' · ' + window.reviewAPI.judge(f));
        } else {
          const state = r?.status === 'postponed' ? 'Postponed' : r?.status === 'cancelled' ? 'Cancelled' : 'Pending';
          tile.innerHTML = label + '<br>' + state;
        }
      }
    }
    function restore() {
      window.reviewAPI.importCSV(snapshot.csv);
      try { localStorage.setItem(seedKey, digest); } catch {}
      sourceNote('Verified morning results loaded.');
      decorate();
    }
    if (!seedApplied) restore();
    else { sourceNote('Saved browser results retained; restore the sourced snapshot if needed.'); decorate(); }
    const toolbar = document.querySelector('#judgeMode').parentElement;
    const restoreButton = document.createElement('button');
    restoreButton.id = 'restoreMorningResults';
    restoreButton.textContent = 'Restore morning results';
    restoreButton.addEventListener('click', restore);
    toolbar.appendChild(restoreButton);
    new MutationObserver(decorate).observe(tiles, {childList: true});
    if (JSON.stringify(window.reviewAPI.getData().forecasts) !== originalForecasts) throw Error('Result bootstrap changed forecasts');
    window.checkedResultsReady = {checked_at: snapshot.checked_at, csv_sha256: digest, originalForecasts, restore};
  }
  install();
})();
