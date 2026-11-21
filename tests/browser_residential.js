window.addEventListener('load', () => setTimeout(() => {
  const checks=[];
  function check(condition,message){if(!condition)throw new Error(message);checks.push(message);}
  const output=document.createElement('pre');output.id='residential-test-output';
  try{
    check(document.querySelectorAll('#rows tr').length===50,'50 municipal rows');
    check(document.querySelectorAll('#map-province [data-munid]').length===414,'414 province polygons');
    check(document.querySelectorAll('#map-south [data-munid]').length===414,'414 inset polygons');
    check(document.getElementById('headline').textContent.includes('54,032'),'annual total starts');
    const toronto=municipalities.find(r=>r.municipality==='Toronto');
    city.value=toronto.MUNID;city.dispatchEvent(new Event('change'));
    check(document.getElementById('details').textContent.includes('10,561'),'Toronto annual starts');
    check(province.getAttribute('viewBox')===data.provinceView&&detail.getAttribute('viewBox')!==data.southView,'inset selection preserves province');
    kind.value='houses';kind.dispatchEvent(new Event('change'));
    check(document.getElementById('headline').textContent.includes('15,033'),'houses exclude apartment counts');
    kind.value='apartment_other';kind.dispatchEvent(new Event('change'));
    check(document.getElementById('headline').textContent.includes('38,999'),'separate apartment and other counts');
    check(detail.querySelector(`[data-munid="${toronto.MUNID}"]`).getAttribute('fill')===fill(9712),'apartment selection changes map counts');
    metric.value='completions';kind.value='total';metric.dispatchEvent(new Event('change'));
    check(document.getElementById('headline').textContent.includes('60,786')&&document.getElementById('stats').textContent.includes('42/50'),'completion counts and coverage');
    const sarnia=municipalities.find(r=>r.municipality==='Sarnia');display(sarnia.MUNID);
    check(document.getElementById('details').textContent.includes('No data')&&detail.querySelector(`[data-munid="${sarnia.MUNID}"]`).getAttribute('fill')===data.missingColor,'missing completions stay missing');
    const search=document.getElementById('search');search.value='Toronto';search.dispatchEvent(new Event('input'));
    check(document.querySelectorAll('#rows tr').length===1,'city search filters table');
    document.getElementById('reset').click();check(detail.getAttribute('viewBox')===data.southView,'reset restores inset');
    output.textContent=JSON.stringify({passed:true,checks});
  }catch(error){output.textContent=JSON.stringify({passed:false,error:String(error),checks});}
  document.body.append(output);
},150));
