/* Append to a temporary copy of the generated HTML and run in headless Chrome. */
window.addEventListener('load', () => setTimeout(() => {
  const checks = [];
  function check(condition, message) {
    if (!condition) throw new Error(message);
    checks.push(message);
  }
  const output = document.createElement('pre');
  output.id = 'bff-evidence-test-output';
  try {
    check(document.querySelectorAll('#rows tr').length === 18, '18 confirmed allocation rows');
    check(document.querySelectorAll('#map-province .municipality').length === 414, '414 province polygons');
    check(document.querySelectorAll('#map-south .municipality').length === 414, '414 inset polygons');
    check(document.getElementById('headline').textContent.includes('18 of 50'), 'confirmed allocations headline');
    check(document.querySelectorAll('#legend .swatch').length === 2, 'confirmed funding and neutral context legend');
    const welland = municipalities.find(r => r.municipality === 'Welland');
    city.value = welland.MUNID;
    city.dispatchEvent(new Event('change'));
    check(document.querySelectorAll('#map-province [data-munid]').length === 18 && document.querySelectorAll('#map-south [data-munid]').length === 18, 'only the 18 confirmed allocations are interactive');
    check(detail.getAttribute('viewBox') !== data.southView, 'selection zooms inset');
    check(province.getAttribute('viewBox') === data.provinceView, 'province remains visible');
    const london = municipalities.find(r => r.municipality === 'London');
    display(london.MUNID);
    check(municipalities.length === 18 && municipalities.every(r=>r.category==='award_confirmed') && !('target' in london), 'funding presentation contains only confirmed allocations');
    check(document.getElementById('details').querySelector('a').href.startsWith('https://www.ola.org/'), 'municipal source link');
    check(!/not verified|unknown|not available|pending verification/i.test(document.body.innerText), 'no unverified category or missing-value fields in the presentation');
    const search = document.getElementById('search');
    search.value = 'Welland';
    search.dispatchEvent(new Event('input'));
    check(document.querySelectorAll('#rows tr').length === 1, 'municipality search');
    document.getElementById('reset').click();
    check(detail.getAttribute('viewBox') === data.southView, 'reset restores inset');
    output.textContent = JSON.stringify({passed: true, checks});
  } catch (error) {
    output.textContent = JSON.stringify({passed: false, error: String(error), checks});
  }
  document.body.append(output);
}, 150));
