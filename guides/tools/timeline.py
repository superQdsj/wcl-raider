"""单轨时间轴（和金标准潜行者·毒牙祭坛同款）：一场录像里关键技能交在哪，标签写「免疫X / 清X」。

用法：把 GOLD_TL_CSS 放进页面 <style>，把 timeline(...) 的结果放进 .tl-card > .tl-scroll。
  bands: [(开始, 结束, 名称, 'boss'|'trash')]，时间写 'm:ss'
  marks: [(时间, 种类, 图标技能ID, 标签)]，种类 ''=主技能(金圈) 'v'=消失(紫) 'e'=闪避(青) 'muted'=可选(灰)
图标用 {{I:技能ID}} 占位，由各页的 build.py 替换。
"""
import re
GOLD_TL_CSS = """/* timeline (same as the gold rogue card) */
.tl-card{margin-top:18px;background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:18px 18px 12px}
.tl-scroll{overflow-x:auto;padding-bottom:6px}
.tl{position:relative;min-width:980px;height:232px}
.band{position:absolute;top:84px;z-index:0;height:30px;border-radius:5px;display:flex;align-items:center;justify-content:center;font-size:12px;white-space:nowrap;overflow:hidden}
.band.trash{background:var(--panel-2);color:var(--faint);border:1px dashed var(--line)}
.band.boss{background:rgba(242,210,75,.12);color:var(--gold);border:1px solid var(--gold-dim);font-weight:700}
.axis{position:absolute;top:212px;font:500 11px var(--mono);color:var(--faint);transform:translateX(-50%)}
.mk{position:absolute;transform:translateX(-50%);display:flex;flex-direction:column;align-items:center;width:80px;z-index:1}
.mk .stem{width:2px;background:var(--gold)}
.mk img{width:22px;height:22px;border-radius:50%;border:2px solid var(--gold);background:#000}
.mk .lab{font-size:12px;line-height:1.3;text-align:center;color:var(--ink)}
.mk .t{font:500 11px var(--mono);color:var(--mute)}
.mk.up{top:4px}
.mk.up .lab{order:0}.mk.up .t{order:1}.mk.up img{order:2}.mk.up .stem{order:3;height:24px}
.mk.dn{top:114px}
.mk.dn .stem{order:0}.mk.dn img{order:1}.mk.dn .t{order:2}.mk.dn .lab{order:3}
.mk.dn .stem{height:14px}
.mk.v .stem{background:var(--shadow)}.mk.v img{border-color:var(--shadow)}
.mk.e .stem{background:var(--nature)}.mk.e img{border-color:var(--nature)}
.mk.muted .stem{background:var(--faint)}.mk.muted img{border-color:var(--faint);filter:grayscale(.7)}.mk.muted .lab{color:var(--mute)}
.mk.end{transform:translateX(-80%)}
.legend{display:flex;flex-wrap:wrap;gap:16px;font-size:12px;color:var(--mute);margin-top:8px}
.legend i{display:inline-block;width:12px;height:12px;border-radius:3px;vertical-align:-2px;margin-right:6px}
"""

def sec(s):
    m, x = s.split(':'); return int(m) * 60 + float(x)

def timeline(end, bands, marks, axis_every=300):
    """bands: (start,end,label,kind); marks: (time, kind '', 'v', 'e', 'muted', icon_id, label). up/dn alternate."""
    p = lambda s: f'{sec(s) / end * 100:.2f}%'
    out = ['<div class="tl">']
    for a, b, lab, k in bands:
        out.append(f'  <div class="band {k}" style="left:{p(a)};width:{(sec(b)-sec(a))/end*100:.2f}%">{lab}</div>')
    t = 0
    while t < end * 0.985:
        st = 'left:0;transform:none' if t == 0 else f'left:{t/end*100:.2f}%'
        out.append(f'  <div class="axis" style="{st}">{t//60}:00</div>'); t += axis_every
    for i, (tm, k, icon, lab) in enumerate(marks):
        cls = ['mk', 'up' if i % 2 == 0 else 'dn'] + ([k] if k else [])
        if i == 0: cls.append("start")
        if sec(tm) / end > 0.94: cls.append('end')
        out.append(f'  <div class="{" ".join(cls)}" style="left:{p(tm)}"><span class="lab">{lab}</span>'
                   f'<span class="t">{tm.split(".")[0]}</span><span class="stem"></span><img src="{{{{I:{icon}}}}}" alt=""></div>')
    out.append('</div>')
    return '\n'.join(out)

