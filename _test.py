# 出题引擎的回归测试：造一个假词库，在无头 Edge 里跑断言，看 <title> 里的结果。
#   用法：python _test.py && <Edge> --headless=new --dump-dom _test.html | grep -o "<title>[^<]*"
# 改完 buildPool / nextQ / answer / caseList 之后跑一遍，别靠肉眼。
import pathlib

TEST = r"""
<script>
var log=[], err=[];
window.onerror=function(m){ err.push(String(m)); };
function t(n,c){ log.push((c?'PASS ':'FAIL ')+n); }
function setTitle(){
  var f = log.filter(function(x){ return x.indexOf('FAIL')===0; }).length;
  document.title = (err.length ? 'ERR:'+err.join(' | ') : 'OK') +
    ' :: ' + (log.length-f) + '/' + log.length + ' PASS' +
    (f ? ' :: ' + log.filter(function(x){ return x.indexOf('FAIL')===0; }).join(' | ') : '') +
    ' :: ' + log.join(' ; ');
}
function optTexts(){ return [].map.call(document.querySelectorAll('#q-opts .opt'), function(b){ return b.textContent; }); }
function pickRight(){
  var w = Q.cur, cn2en = Q.dir==='cn2en', sent = Q.dir==='sent';
  var want = (cn2en||sent) ? w.word : w.cn;
  return [].filter.call(document.querySelectorAll('#q-opts .opt'), function(b){ return b.textContent===want; })[0];
}
function mkQ(pool, dir){
  Q = { pool: pool, i:0, total:pool.length, dir:dir||'en2cn',
        correct:0, wrong:0, combo:0, best:0, served:{},
        endAt: Date.now()+300000, total_ms:300000 };
  tick(); nextQ();
}

/* ---------- 一、真实数据：格式对账 ---------- */
try{
  t('词库非空', WORDS.length > 1500);
  t('每词都有 word/cn/id', WORDS.every(function(w){ return w.word && w.cn && w.id; }));
  t('每词都有音标', WORDS.every(function(w){ return w.phonetic && w.phonetic.charAt(0)==='/'; }));
  t('id 唯一', Object.keys(WORDS.reduce(function(a,w){ a[w.id]=1; return a; },{})).length === WORDS.length);
  t('中文释义含汉字', WORDS.every(function(w){ return /[一-鿿]/.test(w.cn); }));
  // 同释义的词会让四选一出现两个"对"的选项——运行时排掉了，这里只确认数量在预期内
  var byCn = {}, dup = 0;
  WORDS.forEach(function(w){ if(byCn[w.cn]) dup++; else byCn[w.cn]=1; });
  t('同释义组在 30 组以内（实际 '+dup+'）', dup < 30);

  // SENTS：键必须是真词，值必须正好一个 ___
  var sk = Object.keys(SENTS);
  t('有例句数据', sk.length > 1000);
  var allw = {}; WORDS.forEach(function(w){ allw[w.word.toLowerCase()]=1; });
  t('例句的键都在词表里', sk.every(function(k){ return allw[k]; }));
  t('每条例句正好一个空', sk.every(function(k){
      var s=SENTS[k], m=s.match(/___/g); return m && m.length===1; }));
  t('例句都不含中文', sk.every(function(k){ return !/[一-鿿]/.test(SENTS[k]); }));

  // 连答 60 题英译中，3/4 答对
  S = blank(); mkQ(buildPool(), 'en2cn');
  for(var n=0;n<60;n++){
    var bs = document.querySelectorAll('#q-opts .opt');
    if(bs.length!==4) throw new Error('第'+n+'题选项数='+bs.length);
    var rt = pickRight();
    if(!rt) throw new Error('第'+n+'题找不到正确项 '+Q.cur.word);
    if(new Set(optTexts()).size!==4) throw new Error('第'+n+'题选项重复: '+optTexts().join('/'));
    answer(rt, n%4!==0, Q.cur);
    Q.locked=false;
  }
  t('连答 60 题无异常', true);
  t('答完有掌握度记录', Object.keys(S.uw).length>0);
  t('stage 在 0..5', Object.keys(S.uw).every(function(k){ var u=S.uw[k]; return u.stage<=5 && u.stage>=0; }));
  t('todayNew 不超额度', S.app.todayNew <= S.cfg.newLimit);
  t('今日计数对得上', S.app.todayDone === 60 && S.app.todayRight + S.app.todayDone >= 0);
}catch(e){ t('真实数据段抛异常: '+e.message, false); }

/* ---------- 二、假词库：出题池 ---------- */
var fake=[];
for(var i=0;i<400;i++) fake.push({word:'zz'+i, cn:'测试'+i, phonetic:'/z/', full:'n. 释义'+i});
WORDS = fake; WORDS.forEach(function(w,i){ w.id='w'+i; });
SENTS = {};                     // 假词库没有例句
S = blank(); S.cfg.newLimit = 8;

try{
  var iv = interleave([1,2,3,4,5,6,7,8],[9,10]);
  t('interleave 撒开', iv.length===10 && iv.indexOf(9)<6 && iv.indexOf(10)>5);
  t('interleave 无附赠', JSON.stringify(interleave([1,2],[]))==='[1,2]');
  t('interleave 无主体', JSON.stringify(interleave([],[7,8]))==='[7,8]');

  t('冷启动给满每日新词', buildPool().length===8);
  S.app.todayNew = 8;
  t('额度用完且无旧词 → 池子空', buildPool().length===0);
  t('newRoom 归零', newRoom()===0);
  S.app.todayNew = 5;
  t('剩 3 个额度', newRoom()===3);

  // 学过的词进 rest，额度用完时拿它兜底，不能让一轮空着开始
  S = blank(); S.cfg.newLimit = 8;
  var p = buildPool();
  p.slice(0,20).forEach(function(w){ var u=rec(w.id); u.stage=1; u.nextReview=Date.now()+DAY; });
  S.app.todayNew = 8;
  var pf = buildPool();
  t('额度用完拿旧词兜底', pf.length>0 && pf[0].id in S.uw);

  S.app.todayDate = '2000-01-01';
  t('跨天额度重置', newRoom()===8 && S.app.todayNew===0);
  t('跨天清空方向标记', S.app.doneEn2cn===0 && S.app.doneSent===0);

  var p3 = buildPool({'w0':1,'w1':1,'w2':1});
  t('exclude 排除生效', !p3.some(function(w){ return w.id==='w0'||w.id==='w1'||w.id==='w2'; }));

  // 送分题：答熟的词会被撒进池子
  S = blank(); S.cfg.newLimit = 8;
  for(var i=0;i<50;i++){ var u=rec('w'+i); u.stage=5; u.nextReview=Date.now()+DAY; }
  var pg = buildPool();
  t('送分题进池且不超上限', pg.filter(function(w){ return S.uw[w.id] && S.uw[w.id].stage>=5; }).length <= EASY_PER_BATCH);
  // 送分题不能同时出现在主体里（一轮出两遍）
  var ids = pg.map(function(w){ return w.id; });
  t('池内不重复', new Set(ids).size === ids.length);
}catch(e){ t('出题池段抛异常: '+e.message, false); }

/* ---------- 三、SRS 排期 ---------- */
try{
  S = blank(); WORDS = fake; WORDS.forEach(function(w,i){ w.id='w'+i; });
  mkQ([WORDS[0]], 'en2cn');
  answer(pickRight(), true, Q.cur); Q.locked=false;
  var u = S.uw['w0'];
  t('答对升到 1 级', u.stage===1);
  t('下次复习按 1 级排（约 1 天）', Math.abs(u.nextReview-Date.now()-INTERVAL[1]) < 5000);
  for(var i=0;i<4;i++){ mkQ([WORDS[0]],'en2cn'); answer(pickRight(), true, Q.cur); Q.locked=false; }
  t('级数封顶 5', S.uw['w0'].stage===5);

  // 答错：不降级，排到明天；破案进度清零只在已攻克时发生
  S = blank();
  mkQ([WORDS[1]],'en2cn'); answer(pickRight(), true, Q.cur); Q.locked=false;
  var before = S.uw['w1'].stage;
  mkQ([WORDS[1]],'en2cn');
  var wrongBtn = [].filter.call(document.querySelectorAll('#q-opts .opt'), function(b){ return b.textContent!==WORDS[1].cn; })[0];
  answer(wrongBtn, false, WORDS[1]); Q.locked=false;
  t('答错不降级', S.uw['w1'].stage===before);
  t('答错排到明天', Math.abs(S.uw['w1'].nextReview-Date.now()-DAY) < 5000);
  t('答错开始立案', S.uw['w1'].wrong===1 && S.uw['w1'].solved===0 && S.uw['w1'].caseAt>0);
}catch(e){ t('SRS 段抛异常: '+e.message, false); }

/* ---------- 四、中译英队列 ---------- */
try{
  S = blank();
  // 没刷英译中时，队列空、按钮该锁
  show('scr-dir');
  t('没热身时中译英上锁', document.getElementById('btn-cn2en').disabled === true);
  t('锁定文案带锁', document.getElementById('cn2en-lab').textContent.indexOf('🔒')===0);

  // 英译中答对 → 进队首
  mkQ([WORDS[2]],'en2cn'); answer(pickRight(), true, Q.cur); Q.locked=false;
  mkQ([WORDS[3]],'en2cn'); answer(pickRight(), true, Q.cur); Q.locked=false;
  t('答对进中译英队列', S.app.cn2en.length===2);
  t('后答对的在队首', S.app.cn2en[0]==='w3');
  S.app.doneEn2cn = 1;                  // 模拟"今天英译中已经刷过"
  show('scr-dir');
  t('热身过就解锁', document.getElementById('btn-cn2en').disabled === false);

  // 队列出题：题干是中文，选项是英文，不给音标
  var pool = buildCn2enPool();
  t('中译英池子来自队列', pool.some(function(w){ return w.id==='w2'; }));
  mkQ(pool, 'cn2en');
  t('中译英题干是中文', /[一-鿿]/.test(document.getElementById('q-word').textContent));
  t('中译英不给音标', document.getElementById('q-ph').textContent==='');
  t('中译英选项全英文', optTexts().every(function(s){ return /^[A-Za-z]/.test(s); }));
  t('中译英选项不重不漏', new Set(optTexts()).size===4);
  t('答题时不能点发音', document.getElementById('btn-speak').disabled===true);

  var w2 = Q.cur;
  answer(pickRight(), true, w2); Q.locked=false;
  t('考到就出队', S.app.cn2en.indexOf(w2.id)<0);
  t('答完后发音解禁', document.getElementById('btn-speak').disabled===false);

  // 跨天不清队列
  S.app.todayDate='2000-01-01'; rollDay();
  t('跨天不清中译英队列', S.app.cn2en.length===1);
  t('跨天清了方向标记', S.app.doneEn2cn===0);

  // 队列里的词被删掉时自动剔除（改过词表才会出现）
  S.app.cn2en = ['w99','nope'];
  rollDay(); S.app.todayDate='2000-01-02'; rollDay();
  t('队列里的死 id 会被剔掉', S.app.cn2en.indexOf('nope')<0);
}catch(e){ t('中译英段抛异常: '+e.message, false); }

/* ---------- 五、句子练习 ---------- */
try{
  S = blank();
  SENTS = {}; SENTS['zz0'] = 'The ___ is on the desk.';
  t('hasSent 认得出有例句的词', hasSent(WORDS[0]) && !hasSent(WORDS[1]));
  // 把额度开到比词库还大，buildPool 就会把全部 400 个词铺出来，
  // 这样过滤后剩谁是一定的，不受随机性影响
  S.cfg.newLimit = 500;
  var sp = buildSentPool();
  t('句子池只收有例句的词', sp.length===1 && sp[0].id==='w0');
  S.cfg.newLimit = 8;
  mkQ(sp, 'sent');
  t('句子关题干是挖空句', document.getElementById('q-word').innerHTML.indexOf('___')>=0);
  t('句子关不给音标', document.getElementById('q-ph').textContent==='');
  t('句子关选项全英文', optTexts().every(function(s){ return /^[A-Za-z]/.test(s); }));
  t('句子关答题时不能点发音', document.getElementById('btn-speak').disabled===true);

  var sw = Q.cur;
  var wrongBtn2 = [].filter.call(document.querySelectorAll('#q-opts .opt'), function(b){ return b.textContent!==sw.word; })[0];
  answer(wrongBtn2, false, sw); Q.locked=false;
  t('句子关答错把词填回整句', document.getElementById('q-fb').innerHTML.indexOf('zz0')>=0);
  t('句子关答错给出释义', document.getElementById('q-fb').innerHTML.indexOf('释义0')>=0);
  t('答错计入今日答题', S.app.todayDone===1 && S.app.todayRight===0);

  // 没有例句时池子为空，进不去
  SENTS = {}; S = blank();
  t('没例句时句子池为空', buildSentPool().length===0);
}catch(e){ t('句子关段抛异常: '+e.message, false); }

/* ---------- 六、错词本 ---------- */
try{
  S = blank();
  function answerWrong(id){
    mkQ([WORDS.filter(function(w){ return w.id===id; })[0]], 'en2cn');
    var b = [].filter.call(document.querySelectorAll('#q-opts .opt'),
                           function(x){ return x.textContent!==Q.cur.cn; })[0];
    answer(b, false, Q.cur); Q.locked=false;
  }
  function answerRight(id){
    mkQ([WORDS.filter(function(w){ return w.id===id; })[0]], 'en2cn');
    answer(pickRight(), true, Q.cur); Q.locked=false;
  }

  answerWrong('w10');
  t('答错立案', caseKind('w10')==='bad' && caseList('bad').length===1);
  answerRight('w10');
  t('答对 1 次还在本里', caseKind('w10')==='bad' && S.uw['w10'].solved===1);
  answerWrong('w10');
  t('再答错不清零进度', S.uw['w10'].solved===1);
  answerRight('w10'); answerRight('w10');
  t('累计答对 3 次才出本', S.uw['w10'].solved===3 && caseKind('w10')==='');
  answerWrong('w10');
  t('已出本的又答错重新开案', S.uw['w10'].solved===0 && caseKind('w10')==='bad');

  // 慢词：跟自己的平均速度比，慢了只标 fuzzy 不入错词
  S = blank(); S.uw['w11'] = {stage:2, nextReview:0, lastSeen:0, correct:5, wrong:0, fuzzy:0, solved:0, caseAt:0};
  S.app.avgMs = 1000; S.app.msN = 20;
  mkQ([WORDS[11]],'en2cn');
  Q.shownAt = Date.now() - 5000;               // 5 秒，超过 1000*1.6 且超过 2.5 秒
  answer(pickRight(), true, Q.cur); Q.locked=false;
  t('慢答对标记为存疑', S.uw['w11'].fuzzy===1 && caseKind('w11')==='slow');
  t('慢答对不升级', S.uw['w11'].stage===2);
  t('慢答对不算错词', S.uw['w11'].wrong===0);
  t('慢答对不改入册时间以外的进度', S.uw['w11'].solved===0);
}catch(e){ t('错词本段抛异常: '+e.message, false); }

/* ---------- 七、结算与统计 ---------- */
try{
  S = blank();
  mkQ(buildPool(), 'en2cn');
  for(var n=0;n<6;n++){ answer(pickRight(), true, Q.cur); Q.locked=false; if(Q.i>=Q.pool.length) break; }
  var bk = Q.best;
  finish();
  t('结算页显示答对数', document.getElementById('r-correct').textContent===String(bk));
  t('结算记下方向', S.app.doneEn2cn===1);
  t('结算记连续天数', S.app.streak===1 && S.app.lastDay===todayStr());
  t('结算不报错', true);
}catch(e){ t('结算段抛异常: '+e.message, false); }

/* ---------- 八、音效不削顶 ---------- */
setTitle();
try{
  S.cfg.sfx = true;
  var OFF = new (window.OfflineAudioContext || window.webkitOfflineAudioContext)(1, 44100 * 2, 44100);
  var _ac = ac; ac = function(){ return OFF; };
  sfxRight(); sfxWrong();
  ac = _ac; S.cfg.sfx = false;
  OFF.startRendering().then(function(buf){
    var d = buf.getChannelData(0), peak = 0;
    for(var i=0;i<d.length;i++){ var v=Math.abs(d[i]); if(v>peak) peak=v; }
    t('音效峰值不削顶 (peak='+peak.toFixed(2)+')', peak>0.05 && peak<=1);
    setTitle();
  });
}catch(e){ t('离线渲染音效: '+e.message, false); setTitle(); }
</script>
"""

BASE = pathlib.Path(__file__).parent
html = (BASE / "index.html").read_text(encoding="utf-8")
(BASE / "_test.html").write_text(html.replace("</body>", TEST + "</body>"), encoding="utf-8")
print("wrote _test.html")
