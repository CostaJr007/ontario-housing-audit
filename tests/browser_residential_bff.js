window.addEventListener('load',()=>setTimeout(()=>{
  const checks=[];function check(c,m){if(!c)throw new Error(m);checks.push(m);}
  const output=document.createElement('pre');output.id='residential-bff-test-output';
  try{
    check(document.querySelectorAll('#rows tr').length===50,'50 program municipality rows');
    check(document.querySelectorAll('#map-province [data-munid]').length===414,'414 province polygons');
    check(document.querySelectorAll('#map-south [data-munid]').length===414,'414 inset polygons');
    check(municipalities.filter(r=>r.award_confirmed).length===18,'18 confirmed allocations');
    const k=municipalities.find(r=>r.municipality==='Kitchener'),l=municipalities.find(r=>r.municipality==='London'),s=municipalities.find(r=>r.municipality==='Sarnia');
    check(scenario(k).category==='below'&&scenario(l).category==='below','new construction flags two documented cases');
    city.value=k.MUNID;city.dispatchEvent(new Event('change'));
    check(document.getElementById('details').textContent.includes('71.9%')&&document.getElementById('details').textContent.includes('8,013,600'),'Kitchener percentage and award');
    check(detail.getAttribute('viewBox')!==data.southView&&province.getAttribute('viewBox')===data.provinceView,'selection zooms inset only');
    mode.value='independent';mode.dispatchEvent(new Event('change'));
    check(scenario(k).category==='above'&&document.getElementById('details').textContent.includes('85.9%'),'verified ARUs change Kitchener result');
    check(scenario(l).category==='unknown','unknown London ARUs cannot establish failure');
    check(scenario(s).minimum&&scenarioPercent(s).startsWith('≥'),'Sarnia lower bound explicitly marked');
    mode.value='official';mode.dispatchEvent(new Event('change'));
    check(municipalities.filter(r=>scenario(r).category==='above').length===4,'all four official cases pass');
    check(document.querySelectorAll('#map-province .municipality[stroke]').length===18,'blue allocation outlines');
    const search=document.getElementById('search');search.value='London';search.dispatchEvent(new Event('input'));
    check(document.querySelectorAll('#rows tr').length===1,'municipality search');
    document.getElementById('reset').click();check(detail.getAttribute('viewBox')===data.southView,'inset reset');
    output.textContent=JSON.stringify({passed:true,checks});
  }catch(error){output.textContent=JSON.stringify({passed:false,error:String(error),checks});}
  document.body.append(output);
},150));
