"""单轨时间轴（全职业样板同款）：一场录像里关键技能交在哪，标签写机制/动作短名。

用法：把 GOLD_TL_CSS 放进页面 <style>，把 timeline(...) 的结果放进 .tl-card > .tl-scroll。
  bands: [(开始, 结束, 名称, 'boss'|'trash')]，时间写 'm:ss'
  marks: [(时间, 种类, 图标技能ID, 标签)]，种类 ''=主大招(--gold) 'e'=副手牌1(--tl-e / --nature) 'v'=副手牌2(--tl-v / --shadow) 'muted'=顺手/可选(灰)
图例可用 .legend i.pri / .e / .v / .muted / .boss / .trash。
图标用 {{I:技能ID}} 占位，由各页的 build.py 替换。
"""
GOLD_TL_CSS = """/* timeline (shared single-track timeline) */
.tl-card{margin-top:18px;background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:18px 18px 12px}
.tl-scroll{overflow-x:auto;padding-bottom:6px}
.tl{position:relative;min-width:884px;height:232px;margin:0 48px}
.band{position:absolute;top:84px;z-index:0;height:30px;border-radius:5px;display:flex;align-items:center;justify-content:center;font-size:12px;white-space:nowrap;overflow:hidden}
.band.trash{background:var(--panel-2);color:var(--mute);border:1px dashed var(--line)}
.band.boss{background:var(--gold-band,rgba(242,210,75,.12));color:var(--gold);border:1px solid var(--gold-dim);font-weight:700}
.axis{position:absolute;top:212px;font:500 11px var(--mono);color:var(--faint);transform:translateX(-50%)}
.mk{position:absolute;transform:translateX(-50%);display:flex;flex-direction:column;align-items:center;width:96px;z-index:1}
.mk .stem{width:2px;background:var(--gold)}
.mk img{width:22px;height:22px;border-radius:50%;border:2px solid var(--gold);background:var(--ic-edge,#000)}
.mk .lab{font-size:12px;line-height:1.3;text-align:center;color:var(--ink);white-space:nowrap}
.mk .t{font:500 11px/1.25 var(--mono);color:var(--mute)}
.mk.up{bottom:148px}
.mk.up .lab{order:0}.mk.up .t{order:1}.mk.up img{order:2}.mk.up .stem{order:3;height:24px}
.mk.dn{top:114px}
.mk.dn .stem{order:0}.mk.dn img{order:1}.mk.dn .t{order:2}.mk.dn .lab{order:3}
.mk.dn .stem{height:14px}
.mk.v .stem{background:var(--tl-v,var(--shadow))}.mk.v img{border-color:var(--tl-v,var(--shadow))}
.mk.e .stem{background:var(--tl-e,var(--nature))}.mk.e img{border-color:var(--tl-e,var(--nature))}
.mk.muted .stem{background:var(--faint)}.mk.muted img{border-color:var(--faint);filter:grayscale(.7)}.mk.muted .lab{color:var(--mute)}
.legend{display:flex;flex-wrap:wrap;gap:16px;font-size:12px;color:var(--mute);margin-top:8px}
.legend i{display:inline-block;width:12px;height:12px;border-radius:3px;vertical-align:-2px;margin-right:6px}
.legend i.pri{border:2px solid var(--gold);border-radius:50%}
.legend i.e{border:2px solid var(--tl-e,var(--nature));border-radius:50%}
.legend i.v{border:2px solid var(--tl-v,var(--shadow));border-radius:50%}
.legend i.muted{border:2px solid var(--faint);border-radius:50%}
.legend i.boss{background:var(--gold-band,rgba(242,210,75,.12));border:1px solid var(--gold-dim)}
.legend i.trash{background:var(--panel-2);border:1px dashed var(--line)}
"""


def sec(s):
    m, x = s.split(':'); return int(m) * 60 + float(x)


def timeline(end, bands, marks, axis_every=300):
    """bands: (start,end,label,kind); marks: (time, kind ''/'e'/'v'/'muted', icon_id, label). up/dn alternate."""
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
        out.append(f'  <div class="{" ".join(cls)}" style="left:{p(tm)}"><span class="lab">{lab}</span>'
                   f'<span class="t">{tm.split(".")[0]}</span><span class="stem"></span><img src="{{{{I:{icon}}}}}" alt=""></div>')
    out.append('</div>')
    return '\n'.join(out)
