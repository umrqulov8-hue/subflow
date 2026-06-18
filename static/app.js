var SUPABASE_URL='https://kehjabkmrgpfjfbvwfab.supabase.co';
var SUPABASE_KEY='sb_publishable_veNIaaa-jgaKhb3jU3-HqA_u5q4dol2';
var supabase=window.supabase.createClient(SUPABASE_URL,SUPABASE_KEY);

var files=[];
var engine='free';
var currentUser=null;
var currentSession=null;

window.addEventListener('load',function(){
  var dz=document.getElementById('uploadArea');
  var fi=document.getElementById('fileInput');
  if(!dz||!fi){return}

  fi.onchange=function(){
    if(this.files.length){
      for(var i=0;i<this.files.length;i++){
        if(files.length<10)files.push(this.files[i]);
      }
      renderFiles();
      this.value='';
    }
  };

  dz.ondragover=function(e){e.preventDefault();this.classList.add('dragover')};
  dz.ondragleave=function(e){e.preventDefault();this.classList.remove('dragover')};
  dz.ondrop=function(e){
    e.preventDefault();this.classList.remove('dragover');
    var dropped=e.dataTransfer.files;
    for(var i=0;i<dropped.length;i++){
      var n=dropped[i].name;
      if((n.endsWith('.srt')||n.endsWith('.ass'))&&files.length<10)files.push(dropped[i]);
    }
    renderFiles();
  };

  var tb=document.getElementById('translateBtn');
  if(tb)tb.onclick=startTranslate;
  var gs=document.getElementById('getStarted');
  if(gs)gs.onclick=function(){document.querySelector('.app').scrollIntoView({behavior:'smooth'})};
  var cf=document.getElementById('clearFiles');
  if(cf)cf.onclick=function(){files=[];renderFiles()};

  setupAuth();
  setupPayment();
  setupSubscription();
  setEngine('free');
  checkSession();
});

function renderFiles(){
  var dz=document.getElementById('uploadArea');
  var fq=document.getElementById('fileQueue');
  var fl=document.getElementById('fqList');
  var tb=document.getElementById('translateBtn');
  if(!files.length){
    fq.style.display='none';tb.disabled=true;dz.classList.remove('selected');
    dz.querySelector('.dz-title').textContent='Drop subtitle files here';
    dz.querySelector('.dz-sub').textContent='or click to browse · .srt / .ass · up to 10 files';
    return;
  }
  dz.classList.add('selected');
  dz.querySelector('.dz-title').textContent=files.length+' file(s) selected';
  dz.querySelector('.dz-sub').textContent=(10-files.length)+' more can be added · click to change';
  tb.disabled=false;fq.style.display='block';
  var html='';
  for(var i=0;i<files.length;i++){
    var f=files[i];
    var sz=f.size<1024?f.size+' B':f.size<1048576?(f.size/1024).toFixed(1)+' KB':(f.size/1048576).toFixed(1)+' MB';
    html+='<div class="fq-item"><span class="fq-icon">📄</span><span class="fq-name">'+f.name+'</span><span class="fq-size">'+sz+'</span><button class="fq-remove" onclick="removeFile('+i+')">✕</button></div>';
  }
  fl.innerHTML=html;
}

function removeFile(i){files.splice(i,1);renderFiles()}

function setEngine(e){
  if(e==='pro'&&!currentUser){requireAuth();return}
  if(e==='pro'&&currentUser&&currentUser.subscription_status!=='active'){openPayModal();return}
  engine=e;
  var ef=document.getElementById('engineFree');
  var ep=document.getElementById('enginePro');
  var ei=document.getElementById('engineInfo');
  var ub=document.getElementById('usageBox');
  if(ef)ef.classList.toggle('active',e==='free');
  if(ep)ep.classList.toggle('active',e==='pro');
  if(ei){
    if(e==='pro'){
      ei.innerHTML='<span class="ei-icon">✦</span><div><div class="ei-name">DeepL AI</div><div class="ei-desc">Pro · Best quality</div></div>';
      loadUsage();
    }else{
      ei.innerHTML='<span class="ei-icon">⚡</span><div><div class="ei-name">Google Translate</div><div class="ei-desc">Free · Unlimited</div></div>';
      if(ub)ub.style.display='none';
    }
  }
}

var engineFree=document.getElementById('engineFree');
var enginePro=document.getElementById('enginePro');
if(engineFree)engineFree.onclick=function(){setEngine('free')};
if(enginePro)enginePro.onclick=function(){setEngine('pro')};

function startTranslate(){
  if(!files.length)return;
  var tb=document.getElementById('translateBtn');
  var pb=document.getElementById('progressBox');
  var rb=document.getElementById('resultBox');
  var tl=document.getElementById('targetLang');
  tb.classList.add('loading');tb.disabled=true;rb.style.display='none';pb.style.display='block';
  showProgress();
  var results=[];var idx=0;
  function next(){
    if(idx>=files.length){
      pb.style.display='none';showResult(results);tb.classList.remove('loading');tb.disabled=false;
      if(engine==='pro')loadUsage();
      return;
    }
    var f=files[idx];
    setPfi(f.name,'upload');
    var fd=new FormData();fd.append('file',f);
    fetch('/upload',{method:'POST',body:fd}).then(function(r){return r.json()}).then(function(d){
      setPfi(f.name,'trans');
      doTranslate(d.file_id,f.name,tl.value,engine).then(function(res){
        results.push(res);setPfi(f.name,'done');idx++;setPbPct(idx,files.length);next();
      });
    }).catch(function(e){
      results.push({name:f.name,error:e.message});setPfi(f.name,'err');idx++;setPbPct(idx,files.length);next();
    });
  }
  next();
}

function doTranslate(fid,name,tgt,eng){
  return new Promise(function(resolve){
    var url='/translate_progress?file_id='+fid+'&source=auto&target='+tgt+'&engine='+eng;
    if(currentSession&&currentSession.access_token){url+='&token='+encodeURIComponent(currentSession.access_token);}
    var es=new EventSource(url);
    es.onmessage=function(e){
      var d=JSON.parse(e.data);
      if(d.type==='complete'){es.close();resolve({name:name,download:d.download,filename:d.filename})}
      else if(d.type==='error'){es.close();resolve({name:name,error:d.message})}
    };
    es.onerror=function(){es.close();resolve({name:name,error:'Connection error'})};
  });
}

function setPfi(name,s){
  var pf=document.getElementById('pbFiles');if(!pf)return;
  var items=pf.querySelectorAll('.pfi');
  for(var i=0;i<items.length;i++){
    if(items[i].getAttribute('data-n')===name){
      items[i].className='pfi pfi-'+s;
      var st=items[i].querySelector('.pfi-status');
      if(s==='upload')st.textContent='⬆ uploading';
      else if(s==='trans')st.textContent='⟳ translating...';
      else if(s==='done')st.textContent='✓ done';
      else st.textContent='✕ error';
    }
  }
}

function setPbPct(done,total){
  var p=Math.round(done/total*100);
  var pp=document.getElementById('pbPct');var pf=document.getElementById('pbFill');var pt=document.getElementById('pbText');
  if(pp)pp.textContent=p+'%';if(pf)pf.style.width=p+'%';if(pt)pt.textContent=done+' / '+total+' files complete';
}

function showProgress(){
  var pp=document.getElementById('pbPct');var pt=document.getElementById('pbText');var pf=document.getElementById('pbFill');var pb=document.getElementById('pbFiles');
  if(pp)pp.textContent='0%';if(pt)pt.textContent='Preparing...';if(pf)pf.style.width='0%';
  if(pb){var h='';for(var i=0;i<files.length;i++){h+='<div class="pfi pfi-wait" data-n="'+files[i].name+'"><span class="pfi-name">'+files[i].name+'</span><span class="pfi-status">⏳ queued</span></div>';}pb.innerHTML=h;}
}

function showResult(results){
  var rb=document.getElementById('resultBox');var ok=[];var fail=[];
  for(var i=0;i<results.length;i++){if(results[i].error)fail.push(results[i]);else ok.push(results[i]);}
  var h='<div class="rb-title">✓ '+ok.length+' / '+results.length+' files translated</div>';
  if(ok.length){
    h+='<div class="rb-list">';
    for(var i=0;i<ok.length;i++){h+='<div class="rb-item"><span class="rb-name">'+ok[i].name+'</span><button class="rb-dl" onclick="dl(\''+ok[i].download+'\',\''+ok[i].filename+'\')">Download ↓</button></div>';}
    h+='</div>';
    if(ok.length>1)h+='<button class="rb-all" onclick="dlAll()">Download All ↓</button>';
    window._dlResults=ok;
  }
  if(fail.length){h+='<div class="rb-err">';for(var i=0;i<fail.length;i++)h+=fail[i].name+': '+fail[i].error+'<br>';h+='</div>';}
  h+='<br><button class="rb-again" onclick="resetAll()">Translate Another →</button>';
  rb.innerHTML=h;rb.style.display='block';
}

function dl(url,fn){var a=document.createElement('a');a.href=url;a.download=fn;a.click()}
function dlAll(){var arr=window._dlResults||[];for(var i=0;i<arr.length;i++){(function(r){setTimeout(function(){var a=document.createElement('a');a.href=r.download;a.download=r.filename;a.click()},i*200)})(arr[i]);}}
function resetAll(){files=[];var fi=document.getElementById('fileInput');if(fi)fi.value='';renderFiles();var rb=document.getElementById('resultBox');var pb=document.getElementById('progressBox');var ub=document.getElementById('usageBox');if(rb)rb.style.display='none';if(pb)pb.style.display='none';if(ub)ub.style.display='none';}

function loadUsage(){
  var headers={};
  if(currentSession&&currentSession.access_token){headers['Authorization']='Bearer '+currentSession.access_token;}
  fetch('/usage',{headers:headers}).then(function(r){return r.json()}).then(function(d){
    var pct=d.limit>0?Math.round(d.used/d.limit*100):0;
    var uc=document.getElementById('usageCircle');var up=document.getElementById('usagePct');var us=document.getElementById('usageSub');var ub=document.getElementById('usageBox');
    if(uc)uc.style.strokeDashoffset=264-(264*pct/100);if(up)up.textContent=pct+'%';if(us)us.textContent='of 1M chars';if(ub)ub.style.display='block';
  }).catch(function(){});
}

// ─── Supabase Auth ───
function setupAuth(){
  var modal=document.getElementById('authModal');var close=document.getElementById('authClose');
  var tabSi=document.getElementById('tabSignin');var tabSu=document.getElementById('tabSignup');
  var siForm=document.getElementById('signinForm');var suForm=document.getElementById('signupForm');
  var navSi=document.getElementById('navSignin');var navSu=document.getElementById('navSignup');
  var navOut=document.getElementById('navSignout');var siErr=document.getElementById('siErr');var suErr=document.getElementById('suErr');

  function openModal(tab){
    modal.style.display='flex';siErr.textContent='';suErr.textContent='';
    if(tab==='signup'){tabSu.classList.add('active');tabSi.classList.remove('active');suForm.style.display='flex';siForm.style.display='none';}
    else{tabSi.classList.add('active');tabSu.classList.remove('active');siForm.style.display='flex';suForm.style.display='none';}
  }
  function closeModal(){modal.style.display='none'}
  if(close)close.onclick=closeModal;
  modal.onclick=function(e){if(e.target===modal)closeModal()};
  if(navSi)navSi.onclick=function(){openModal('signin')};
  if(navSu)navSu.onclick=function(){openModal('signup')};
  if(tabSi)tabSi.onclick=function(){tabSi.classList.add('active');tabSu.classList.remove('active');siForm.style.display='flex';suForm.style.display='none';siErr.textContent=''};
  if(tabSu)tabSu.onclick=function(){tabSu.classList.add('active');tabSi.classList.remove('active');suForm.style.display='flex';siForm.style.display='none';suErr.textContent=''};

  // Sign In with Supabase
  if(siForm)siForm.onsubmit=function(e){
    e.preventDefault();
    var email=document.getElementById('siEmail').value;
    var pass=document.getElementById('siPass').value;
    siErr.textContent='';
    supabase.auth.signInWithPassword({email:email,password:pass})
    .then(function(result){
      if(result.error){siErr.textContent=result.error.message;return;}
      currentSession=result.data.session;
      currentUser={
        logged_in:true,
        id:result.data.user.id,
        email:result.data.user.email,
        name:result.data.user.user_metadata&&result.data.user.user_metadata.name?result.data.user.user_metadata.name:result.data.user.email,
        plan:'free',
        subscription_status:'none'
      };
      loadSubscription();
      updateNavAuth();
      closeModal();
    }).catch(function(err){siErr.textContent='Connection error';});
  };

  // Sign Up with Supabase
  if(suForm)suForm.onsubmit=function(e){
    e.preventDefault();
    var name=document.getElementById('suName').value;
    var email=document.getElementById('suEmail').value;
    var pass=document.getElementById('suPass').value;
    suErr.textContent='';
    supabase.auth.signUp({email:email,password:pass,options:{data:{name:name}}})
    .then(function(result){
      if(result.error){suErr.textContent=result.error.message;return;}
      if(result.data&&result.data.user&&result.data.user.identities&&result.data.user.identities.length===0){
        suErr.textContent='Email already registered';return;
      }
      if(result.data.session){
        currentSession=result.data.session;
        currentUser={
          logged_in:true,
          id:result.data.user.id,
          email:result.data.user.email,
          name:name,
          plan:'free',
          subscription_status:'none'
        };
        loadSubscription();
        updateNavAuth();
        closeModal();
      }else{
        siErr.textContent='Check your email for confirmation link.';
        tabSi.click();
      }
    }).catch(function(err){suErr.textContent='Connection error';});
  };

  // Sign Out
  if(navOut)navOut.onclick=function(){
    supabase.auth.signOut().then(function(){
      currentUser=null;currentSession=null;updateNavAuth();
    });
  };
}

function checkSession(){
  supabase.auth.getSession().then(function(result){
    if(result.data.session){
      currentSession=result.data.session;
      var user=result.data.session.user;
      currentUser={
        logged_in:true,
        id:user.id,
        email:user.email,
        name:user.user_metadata&&user.user_metadata.name?user.user_metadata.name:user.email,
        plan:'free',
        subscription_status:'none'
      };
      loadSubscription();
      updateNavAuth();
    }
  });

  supabase.auth.onAuthStateChange(function(event,session){
    if(event==='SIGNED_IN'&&session){
      currentSession=session;
      var user=session.user;
      currentUser={
        logged_in:true,
        id:user.id,
        email:user.email,
        name:user.user_metadata&&user.user_metadata.name?user.user_metadata.name:user.email,
        plan:'free',
        subscription_status:'none'
      };
      loadSubscription();
      updateNavAuth();
    }else if(event==='SIGNED_OUT'){
      currentUser=null;currentSession=null;updateNavAuth();
    }
  });
}

function loadSubscription(){
  if(!currentUser||!currentSession)return;
  var headers={'Content-Type':'application/json','Authorization':'Bearer '+currentSession.access_token};
  fetch('/api/subscription',{headers:headers}).then(function(r){return r.json()}).then(function(d){
    if(d.subscription){
      currentUser.subscription_status=d.subscription.status||'none';
      currentUser.expires_at=d.subscription.expires_at||0;
      currentUser.plan=d.subscription.status==='active'?'pro':'free';
    }
    updateNavAuth();
  }).catch(function(){});
}

function updateNavAuth(){
  var navAuth=document.getElementById('navAuth');var navUser=document.getElementById('navUser');
  var navName=document.getElementById('navUserName');var navPlan=document.getElementById('navUserPlan');
  if(currentUser&&currentUser.logged_in){
    if(navAuth)navAuth.style.display='none';
    if(navUser)navUser.style.display='flex';
    if(navName)navName.textContent=currentUser.name||currentUser.email;
    if(navPlan){
      if(currentUser.subscription_status==='active'){navPlan.textContent='Pro';navPlan.style.display='inline-block';}
      else{navPlan.style.display='none';}
    }
    if(currentUser.subscription_status==='active')setEngineSilent('pro');
  }else{
    if(navAuth)navAuth.style.display='flex';
    if(navUser)navUser.style.display='none';
    setEngineSilent('free');
  }
}

function setEngineSilent(e){
  engine=e;
  var ef=document.getElementById('engineFree');var ep=document.getElementById('enginePro');
  var ei=document.getElementById('engineInfo');var ub=document.getElementById('usageBox');
  if(ef)ef.classList.toggle('active',e==='free');if(ep)ep.classList.toggle('active',e==='pro');
  if(ei){
    if(e==='pro'){ei.innerHTML='<span class="ei-icon">✦</span><div><div class="ei-name">DeepL AI</div><div class="ei-desc">Pro · Best quality</div></div>';loadUsage();}
    else{ei.innerHTML='<span class="ei-icon">⚡</span><div><div class="ei-name">Google Translate</div><div class="ei-desc">Free · Unlimited</div></div>';if(ub)ub.style.display='none';}
  }
}

function requireAuth(){
  var modal=document.getElementById('authModal');if(modal)modal.style.display='flex';
  showProGate('Sign in to continue');
}

function showProGate(msg){
  var existing=document.querySelector('.pro-gate');if(existing)existing.remove();
  var el=document.createElement('div');el.className='pro-gate';el.textContent=msg;
  document.body.appendChild(el);setTimeout(function(){el.remove()},3000);
}

// ─── Payment ───
function setupPayment(){
  var modal=document.getElementById('payModal');var close=document.getElementById('payClose');
  if(close)close.onclick=function(){modal.style.display='none'};
  if(modal)modal.onclick=function(e){if(e.target===modal)modal.style.display='none'};
}

function startTspayPayment(){
  if(!currentUser||!currentSession){requireAuth();return}
  var err=document.getElementById('payErr');var btn=document.getElementById('payBtn');
  err.textContent='';btn.textContent='Creating payment...';btn.disabled=true;

  var headers={'Content-Type':'application/json','Authorization':'Bearer '+currentSession.access_token};
  fetch('/api/create-payment',{method:'POST',headers:headers,body:JSON.stringify({plan:'pro'})})
  .then(function(r){return r.json()}).then(function(d){
    if(d.error){err.textContent=d.error;btn.textContent='Pay $5.49 with TSPay';btn.disabled=false;return;}
    if(d.payment_url){window.location.href=d.payment_url;}
    else{err.textContent='No payment URL received';btn.textContent='Pay $5.49 with TSPay';btn.disabled=false;}
  }).catch(function(){err.textContent='Payment failed. Try again.';btn.textContent='Pay $5.49 with TSPay';btn.disabled=false;});
}

function openPayModal(){
  if(!currentUser||!currentSession){requireAuth();return}
  var modal=document.getElementById('payModal');
  var err=document.getElementById('payErr');var btn=document.getElementById('payBtn');
  if(err)err.textContent='';
  if(btn){btn.textContent='Pay $5.49 with TSPay';btn.disabled=false;}
  modal.style.display='flex';
}

function closePayModal(){document.getElementById('payModal').style.display='none'}

// ─── Subscription Management ───
function setupSubscription(){
  var navSub=document.getElementById('navSubBtn');
  if(navSub)navSub.onclick=openSubModal;
  var close=document.getElementById('subClose');
  if(close)close.onclick=function(){document.getElementById('subModal').style.display='none'};
  var modal=document.getElementById('subModal');
  if(modal)modal.onclick=function(e){if(e.target===modal)modal.style.display='none'};
}

function openSubModal(){
  if(!currentUser||!currentSession){requireAuth();return}
  var modal=document.getElementById('subModal');modal.style.display='flex';
  var status=document.getElementById('subStatus');
  var usage=document.getElementById('subUsage');
  var details=document.getElementById('subDetails');
  var actions=document.getElementById('subActions');
  status.innerHTML='<div style="text-align:center;padding:8px;color:var(--text3)">Loading...</div>';
  usage.innerHTML='';details.innerHTML='';actions.innerHTML='';

  var headers={'Authorization':'Bearer '+currentSession.access_token};
  fetch('/api/subscription',{headers:headers}).then(function(r){return r.json()}).then(function(d){
    var sub=d.subscription;var u=d.usage;var last=d.last_payment;
    var isActive=sub.status==='active';
    var expiresDate=sub.expires_at?new Date(sub.expires_at*1000).toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'}):'—';

    status.className='sub-status '+(isActive?'sub-status-active':'sub-status-inactive');
    status.innerHTML='<span class="ss-badge '+(isActive?'ss-badge-active':'ss-badge-none')+'">'+(isActive?'ACTIVE':'INACTIVE')+'</span>'+
      '<div class="ss-text">'+(isActive?'Pro subscription active':'No active subscription')+'</div>'+
      (isActive?'<div class="ss-date">Renews '+expiresDate+(sub.auto_renew?' (auto)':' (manual)')+'</div>':'');

    var pct=u.limit>0?Math.round(u.used/u.limit*100):0;
    usage.className='sub-usage';
    usage.innerHTML='<div class="su-label">CHARACTERS USED THIS MONTH</div>'+
      '<div class="su-bar"><div class="su-fill" style="width:'+pct+'%"></div></div>'+
      '<div class="su-info"><span>'+u.used.toLocaleString()+' / '+u.limit.toLocaleString()+'</span><span>'+pct+'%</span></div>';

    var methods=d.payment_methods||[];
    var cardInfo=methods.length>0?methods[methods.length-1].card_masked:'No card on file';
    details.className='sub-details';
    details.innerHTML='<div class="sd-row"><span>Plan</span><span>Pro ($5.49/mo)</span></div>'+
      '<div class="sd-row"><span>Card</span><span>'+cardInfo+'</span></div>'+
      (last?'<div class="sd-row"><span>Last Payment</span><span>$'+last.amount+' · '+new Date(last.created_at*1000).toLocaleDateString()+'</span></div>':'')+
      '<div class="sd-row"><span>Auto-renew</span><span>'+(sub.auto_renew?'On':'Off')+'</span></div>';

    actions.className='sub-actions';
    if(isActive){
      if(sub.auto_renew){
        actions.innerHTML='<button class="mbtn" style="border:1px solid var(--border);background:var(--bg);color:var(--text)" onclick="cancelSub()">Cancel Auto-renew</button>';
      }else{
        actions.innerHTML='<button class="mbtn mbtn-dark" onclick="reactivateSub()">Re-enable Auto-renew</button>';
      }
    }else{
      actions.innerHTML='<button class="mbtn mbtn-dark" onclick="closeSubModal();openPayModal()">Subscribe to Pro</button>';
    }
  }).catch(function(){
    status.innerHTML='<div class="ss-text" style="color:var(--red)">Failed to load subscription</div>';
  });
}

function cancelSub(){
  var headers={'Authorization':'Bearer '+currentSession.access_token};
  fetch('/api/cancel',{method:'POST',headers:headers}).then(function(r){return r.json()}).then(function(d){
    showProGate(d.message||'Auto-renew cancelled');openSubModal();
  });
}

function reactivateSub(){
  var headers={'Authorization':'Bearer '+currentSession.access_token};
  fetch('/api/reactivate',{method:'POST',headers:headers}).then(function(r){return r.json()}).then(function(d){
    showProGate(d.message||'Auto-renew enabled');openSubModal();
  });
}

function closeSubModal(){document.getElementById('subModal').style.display='none'}

// ─── Pricing Buttons ───
var subBtn=document.querySelector('.pc-btn-glow');
if(subBtn)subBtn.onclick=function(){
  if(!currentUser||!currentSession){requireAuth();return}
  if(currentUser.subscription_status==='active'){showProGate('You already have Pro!');return}
  openPayModal();
};
var pricingBtns=document.querySelectorAll('.pc-btn');
for(var i=0;i<pricingBtns.length;i++){
  (function(btn){
    if(!btn.classList.contains('pc-btn-glow')){
      btn.onclick=function(){document.querySelector('.app').scrollIntoView({behavior:'smooth'})};
    }
  })(pricingBtns[i]);
}

function openAuthModal(tab){
  var modal=document.getElementById('authModal');if(!modal)return;
  modal.style.display='flex';
  var tabSi=document.getElementById('tabSignin');var tabSu=document.getElementById('tabSignup');
  var siF=document.getElementById('signinForm');var suF=document.getElementById('signupForm');
  if(tab==='signup'){if(tabSu)tabSu.classList.add('active');if(tabSi)tabSi.classList.remove('active');if(suF)suF.style.display='flex';if(siF)siF.style.display='none';}
  else{if(tabSi)tabSi.classList.add('active');if(tabSu)tabSu.classList.remove('active');if(siF)siF.style.display='flex';if(suF)suF.style.display='none';}
}
