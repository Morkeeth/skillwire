/* Dated evidence only. This component never reads or writes community votes. */
(function () {
  'use strict';
  const host = document.querySelector('#weekly-sidebar');
  if (!host) return;
  const node = (tag, text, cls) => {
    const element = document.createElement(tag);
    if (text !== undefined) element.textContent = text;
    if (cls) element.className = cls;
    return element;
  };
  const date = iso => new Date(iso.slice(0, 10) + 'T12:00:00Z').toLocaleDateString('en-GB', {
    day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC'
  });
  const inspect = row => {
    const button = node('button', row.name, 'weekly-skill');
    button.type = 'button';
    button.setAttribute('aria-label', 'Inspect ' + row.name);
    button.onclick = () => {
      if (typeof window.inspect === 'function' && document.querySelector('#skill-count')?.textContent !== '0') {
        window.inspect(row.id);
      } else {
        host.querySelector('[role=status]').textContent = 'The catalog is still loading. Try this skill again shortly.';
      }
    };
    return button;
  };
  async function load() {
    try {
      const response = await fetch('weekly.json', {cache: 'no-cache'});
      if (!response.ok) throw Error('Weekly evidence unavailable');
      const data = await response.json();
      if (data.schema !== 1) throw Error('Weekly evidence unavailable');
      const title = node('div', undefined, 'panel-heading');
      const heading = node('strong', 'Weekly');
      heading.id = 'weekly-title';
      title.append(heading, node('span', 'Week of ' + date(data.week_start)));
      const growth = node('section', undefined, 'weekly-item');
      growth.append(node('h3', 'Fastest growing'));
      const g = data.fastest_growing;
      if (g.status === 'available') {
        growth.append(node('p', date(g.from) + ' to ' + date(g.to)));
        for (const row of g.rows) {
          const item = node('div', undefined, 'weekly-growth-row');
          item.append(inspect(row), node('span', '+' + row.change.toLocaleString('en-GB') + ' reported installs'));
          growth.append(item);
        }
        if (!g.rows.length) growth.append(node('p', 'No positive change among matched entries.'));
        growth.append(node('p', g.reason + ' ' + g.matched_entries + ' matched entries; ' + g.decreased_counters_excluded + ' decreased counters excluded.', 'weekly-note'));
      } else {
        growth.append(node('p', 'Unavailable', 'weekly-unavailable'), node('p', g.reason, 'weekly-note'));
      }
      const feature = node('section', undefined, 'weekly-item');
      feature.append(node('h3', 'Skill of the week'));
      const f = data.skill_of_week;
      if (f.status === 'available') {
        feature.append(inspect(f), node('p', f.repo),
          node('p', f.uses + ' host sessions · 30 days to ' + date(f.counted_at)),
          node('p', f.catalog_relation, 'weekly-note'));
        const method = node('details');
        method.append(node('summary', 'Why this skill?'), node('p', f.method), node('p', f.basis));
        feature.append(method);
      } else feature.append(node('p', 'Unavailable', 'weekly-unavailable'), node('p', f.reason, 'weekly-note'));
      const status = node('p', '', 'weekly-note');
      status.setAttribute('role', 'status');
      host.replaceChildren(title, growth, feature, status);
      host.dataset.state = 'ready';
    } catch (error) {
      const status = node('p', 'Weekly evidence unavailable. Browse host and the catalog remain available.', 'weekly-note');
      status.setAttribute('role', 'status');
      host.replaceChildren(status);
      host.dataset.state = 'unavailable';
    }
  }
  load();
}());
