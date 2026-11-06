import sys,re
S=sys.argv[1]; p=S+'/rogue.src.html'; s=open(p).read()
def R(a,b):
    global s
    assert s.count(a)==1,("MISS",a[:80]); s=s.replace(a,b)
# header
R('''<p class="lede">这个副本几乎全是<b>自然伤害和持续毒</b>。对贼来说，<b>暗影斗篷</b>能清能免，是主要解法：拉维的毒球、扭缠盘蛇的同步毒液、第 8 波的剧毒涌动、尾王的毒牙仪式都靠它。斗篷之外，佯攻顶范围伤害，闪避配天赋顶尾王飞斧。</p>''',
'''<p class="lede">这个副本几乎全是<b>自然伤害和持续毒</b>。贼的核心是<b>暗影斗篷</b>：拉维的毒球、扭缠盘蛇的同步毒液、第 8 波的剧毒涌动、尾王的毒牙仪式，都交斗篷。其余时间佯攻顶范围伤害，闪避顶尾王的飞斧。</p>''')
R('''<span class="chip">数据 <b>3 场 +24 限时 +1</b></span>
      <span class="chip">玩家 <b>敏锐 ×3 · 3 支不同队伍</b></span>
      <span class="chip">适用 <b>斗篷 / 佯攻 / 消失 / 闪避 / 疾跑 三系通用</b></span>
      <span class="chip">日期 <b>2026-10-28</b></span>''',
'''<span class="chip">参考 <b>+24 限时敏锐贼 ×3</b></span>
      <span class="chip">英雄天赋 <b>欺诈者</b></span>
      <span class="chip">适用 <b>斗篷 / 佯攻 / 消失 / 闪避 / 疾跑 三系通用</b></span>''')
# timeline
R('<p class="sub">第一名记录（斗篷小王子，29:48 限时）的 9 次暗影斗篷。金色 = 清掉或免疫了机制；灰色 = 没对上机制。</p>',
  '<p class="sub">一整场 +24 里，暗影斗篷每次交给了谁。冷却一好就留给下一个毒机制。</p>')
s=re.sub(r'\n\s*<div class="mk up muted"[^\n]*</div>','',s)
R('<span>斗篷冷却约 2 分钟，几乎是好了就交给下一个毒机制。</span>','')
# moments
R('<p class="sub">三名贼在三场里都这样处理，证据最硬。</p>','<p class="sub">每把都要做到的四次斗篷。</p>')
R('<p>等毒球打中、血量下来再开，一次清掉 10 秒的持续毒。三名贼都这样打。</p>','<p>等毒球打中、血量下来再开，一次清掉 10 秒的持续毒。</p>')
R('<p>读条时提前开，整段 35 秒的全团毒直接不上身。4 次全部免疫成功。</p>','<p>读条时提前开，35 秒的全团毒直接不上身。</p>')
# evasion section
a=s.index('<section>\n  <h2><span class="k">03</span>'); b=s.index('</section>',a)+len('</section>')
s=s[:a]+'''<section>
  <h2><span class="k">03</span>切骨者：读条结束前开闪避</h2>
  <div class="finding">
    <div>
      <h3><img class="ic lg" src="{{I:5277}}" alt="">闪避 + 天赋「飘忽不定」</h3>
      <p>祖尔加的<b>切骨者</b>是 3 秒读条，飞斧会点名一名玩家，命中后再流血 7 秒。看到读条就开闪避，读条结束前开好即可。</p>
      <p>飞斧躲不掉，开闪避是为了天赋<b>「飘忽不定」</b>：闪避期间受到的所有伤害降低 20%。10 秒的闪避正好盖住飞斧首击和整段流血。</p>
      <p>切骨者是单体伤害，佯攻的范围减伤顶不到它，这里交闪避。</p>
    </div>
    <div class="bars" role="img" aria-label="切骨者流血每跳：不开闪避 22.5 万，开闪避 17.2 万">
      <div class="cap">切骨者流血每跳承伤</div>
      <div class="bar-row"><span>不开闪避</span><div class="bar"><span class="off" style="width:100%">22.5 万</span></div></div>
      <div class="bar-row"><span>开闪避</span><div class="bar"><span class="on" style="width:76.5%">17.2 万</span></div></div>
      <div class="delta">−23%</div>
    </div>
  </div>
</section>'''+s[b:]
# route notes
R('<div class="note">斗篷多半是<b>毒球打中、血量掉到四成左右</b>再开，一次清掉整段持续伤害最划算。这一场里拉维战交了 3 次斗篷。</div>',
  '<div class="note">斗篷在<b>毒球打中、血量掉到四成左右</b>再开，一次清掉整段持续伤害最划算。</div>')
R('<div class="why">需「飘忽不定」，减伤两成</div>','<div class="why">读条结束前开，减伤盖住流血</div>')
R('<div class="note">拦光束可以和奶骑轮流：<b>骑士圣盾一轮、贼斗篷一轮</b>，两队数据里都这样分担。</div>',
  '<div class="note">拦光束可以和奶骑轮流：<b>骑士圣盾一轮、贼斗篷一轮</b>。</div>')
R('<p class="sub">三场每场都用到的保命和机制技能。金框是这个副本的核心。</p>','<p class="sub">金框是这个副本的核心技能。</p>')
R('<dd>切骨者读条时（需「飘忽不定」）</dd>','<dd>切骨者读条时</dd>')
R('<td><span class="no">✗</span> 闪避减伤（需天赋）</td>','<td><span class="no">✗</span> 闪避减伤</td>')
# section 07 -> talents
a=s.index('<section>\n  <h2><span class="k">07</span>'); b=s.index('</section>',a)+len('</section>')
s=s[:a]+'''<section>
  <h2><span class="k">07</span>天赋</h2>
  <p class="sub">三名 +24 敏锐贼用的是同一套天赋，英雄天赋欺诈者。复制下面的字符串，在游戏天赋界面点「导入」即可。</p>
  <div class="talent">
    <div class="code-row">
      <code id="talent-code">{{TALENT}}</code>
      <button type="button" id="copy-btn">复制</button>
    </div>
    <div class="tal-grid">
      <div class="tal key"><img class="ic" src="{{T:79008}}" alt=""><div><b>飘忽不定</b><span>闪避期间受到的伤害降低 20%，佯攻额外减非范围伤害 20%</span></div></div>
      <div class="tal"><img class="ic" src="{{T:423647}}" alt=""><div><b>优雅诡谋</b><span>佯攻 2 次充能，范围伤害段随时有</span></div></div>
      <div class="tal"><img class="ic" src="{{T:1267220}}" alt=""><div><b>危险感知</b><span>20% 几率让受到的伤害降低 20%</span></div></div>
      <div class="tal"><img class="ic" src="{{T:231719}}" alt=""><div><b>麻木神经</b><span>受到的物理伤害降低 5%</span></div></div>
      <div class="tal"><img class="ic" src="{{T:280716}}" alt=""><div><b>吸血药膏</b><span>致命药膏附带吸血</span></div></div>
      <div class="tal"><img class="ic" src="{{T:394931}}" alt=""><div><b>蹈厉奋发</b><span>暗影步多 1 次充能，躲冲锋更从容</span></div></div>
      <div class="tal"><img class="ic" src="{{T:231691}}" alt=""><div><b>强化疾跑</b><span>疾跑冷却缩短 60 秒</span></div></div>
      <div class="tal"><img class="ic" src="{{T:423683}}" alt=""><div><b>轻若鸿毛</b><span>疾跑更快、持续更久</span></div></div>
      <div class="tal"><img class="ic" src="{{T:441247}}" alt=""><div><b>烟雾</b>（欺诈者）<span>惊慌的目标对你造成的伤害降低 5%</span></div></div>
    </div>
    <div class="refs">参考录像：
      <a href="https://www.warcraftlogs.com/reports/1AWhVvdLbpy2gPak#fight=36">斗篷小王子 29:48</a>
      <a href="https://www.warcraftlogs.com/reports/vyTYACGBPHca6qtw#fight=4">Qingxinlucky 29:28</a>
      <a href="https://www.warcraftlogs.com/reports/nJWT6jHVAXvCwYym#fight=11">黑川茜贼贼 29:49</a>
    </div>
  </div>
</section>'''+s[b:]
# css
R('footer{padding:40px 0 56px;','''.talent{margin-top:18px;background:var(--panel);border:1px solid var(--gold-dim);border-radius:14px;padding:18px;display:grid;gap:16px}
.code-row{display:flex;gap:10px;align-items:stretch}
.code-row code{flex:1;min-width:0;font:500 13px/1.5 var(--mono);color:var(--gold);background:var(--bg);border:1px solid var(--line);border-radius:8px;padding:10px 12px;word-break:break-all;user-select:all}
.code-row button{flex:none;font:700 14px var(--body);color:#17140a;background:var(--gold);border:0;border-radius:8px;padding:0 20px;cursor:pointer}
.code-row button:hover{filter:brightness(1.08)}
.code-row button:focus-visible{outline:2px solid var(--ink);outline-offset:2px}
.tal-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:10px}
.tal{display:flex;gap:10px;align-items:center;padding:10px;border:1px solid var(--line);border-radius:10px;background:var(--panel-2);font-size:13px}
.tal b{font-size:14px;margin-right:4px}
.tal span{display:block;color:var(--mute)}
.tal.key{border-color:var(--gold-dim)}
.tal.key b{color:var(--gold)}
.refs{font-size:12.5px;color:var(--faint);display:flex;flex-wrap:wrap;gap:6px 14px}
.refs a{color:var(--mute);border-bottom:1px dotted var(--faint)}
.refs a:hover{color:var(--gold)}
footer{padding:40px 0 56px;''')
R('</footer>','''</footer>
<script>
(function(){
  var btn=document.getElementById("copy-btn"), code=document.getElementById("talent-code");
  btn.addEventListener("click",function(){
    var t=code.textContent.trim();
    function done(){btn.textContent="已复制";setTimeout(function(){btn.textContent="复制";},1600);}
    if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(t).then(done,fallback);}else{fallback();}
    function fallback(){var r=document.createRange();r.selectNodeContents(code);var sel=window.getSelection();sel.removeAllRanges();sel.addRange(r);try{document.execCommand("copy");done();}catch(e){btn.textContent="已选中，按 Ctrl+C";}}
  });
})();
</script>''')
R('wcl-raider · 毒牙祭坛潜行者应对手册 · 数据 Warcraft Logs · 2026-11','潜行者 · 毒牙祭坛 应对手册 · 2026-11')
open(p,'w').write(s)
print('ok')
