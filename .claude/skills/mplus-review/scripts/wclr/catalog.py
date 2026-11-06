"""常见功能技能的分类（只用于标注和排序；不在表里的低频技能仍会被数据规则选中）。

分类：
  驱散      给队友（或自己）驱散减益
  自解      清除自己身上的减益（种族、天赋强化后的技能）
  免疫      免疫伤害/减益（含对队友的保护类）
  反射      法术反射
  减伤      个人减伤、保命
  外部减伤  给队友的减伤
  团队减伤  全队/区域减伤
  解控      解除或免疫定身、减速、昏迷、恐惧等（含给队友）
  位移      位移、加速
  控制      对敌人的昏迷、击退、群控（常用来打断读条或拉开距离）
  消耗品    治疗石、药水
  增益      团队增益（奥术智慧、战斗怒吼等，战斗中补 buff）
  打断      纯打断（另有 interrupts 命令，本命令不展开）
  战复      战斗复活
ID 不存在于本场日志时自动忽略；同名技能按名称匹配作补充。
"""
from __future__ import annotations

from typing import Dict, Optional, Tuple

from .cmd_interrupts import KICK_SPELLS

# gid: (分类, 是否作用于全队/区域)
SPELLS: Dict[int, Tuple[str, bool]] = {
    # ---- 驱散
    4987: ("驱散", False),      # 清洁术 Cleanse
    213644: ("驱散", False),    # 清毒术 Cleanse Toxins
    527: ("驱散", False),       # 纯净术 Purify
    213634: ("驱散", False),    # 净化疾病 Purify Disease
    32375: ("驱散", True),      # 群体驱散 Mass Dispel
    88423: ("驱散", False),     # 自然之愈 Nature's Cure
    2782: ("驱散", False),      # 清除腐蚀 Remove Corruption
    77130: ("驱散", False),     # 净化灵魂 Purify Spirit
    51886: ("驱散", False),     # 净化灵魂 Cleanse Spirit
    383013: ("驱散", True),     # 清毒图腾 Poison Cleansing Totem（驱散事件里的技能是 383015/403922 "清毒"）
    115310: ("驱散", True),     # 还魂术 Revival（魔法 3 个 + 中毒、疾病）
    388615: ("驱散", True),     # 还阳术 Restoral（中毒、疾病；可在昏迷中施放）
    115450: ("驱散", False),    # 清创生血 Detox (织雾)
    218164: ("驱散", False),    # 清创生血 Detox
    360823: ("驱散", False),    # 自然平衡 Naturalize
    365585: ("驱散", False),    # 灼烧之焰 Expunge
    374251: ("驱散", True),     # 灼烧之焰 Cauterizing Flame
    475: ("驱散", False),       # 解除诅咒 Remove Curse
    89808: ("驱散", False),     # 烧灼魔法 Singe Magic（小鬼）
    119905: ("驱散", False),    # 烧灼魔法（指挥恶魔）
    132411: ("驱散", False),    # 烧灼魔法（牺牲）
    # ---- 自解
    20594: ("自解", False),     # 石像形态 Stoneform（矮人）
    265221: ("自解", False),    # 烈焰之血 Fireblood（黑铁矮人）
    65116: ("自解", False),     # 石像形态（增益）
    59752: ("解控", False),     # 生存意志 Will to Survive（人类，只解昏迷）
    7744: ("解控", False),      # 亡灵意志 Will of the Forsaken
    20589: ("解控", False),     # 逃命专家 Escape Artist（侏儒）
    58984: ("减伤", False),     # 影遁 Shadowmeld
    5384: ("自解", False),      # 假死 Feign Death（紧急药膏 459517：清除中毒、疾病）
    186265: ("免疫", False),    # 灵龟守护 Aspect of the Turtle
    31224: ("免疫", False),     # 暗影斗篷 Cloak of Shadows
    1856: ("自解", False),      # 消失 Vanish
    47585: ("减伤", False),     # 消散 Dispersion（免疫移动限制）
    # ---- 免疫
    642: ("免疫", False),       # 圣盾术 Divine Shield
    1022: ("免疫", False),      # 保护祝福 Blessing of Protection
    204018: ("免疫", False),    # 破咒祝福 Blessing of Spellwarding
    45438: ("免疫", False),     # 寒冰屏障 Ice Block
    414658: ("减伤", False),    # 深寒凝冰 Ice Cold（替代寒冰屏障，无免疫）
    48707: ("免疫", False),     # 反魔法护罩 Anti-Magic Shell（不屈意志 457574：开启时移除魔法效果）
    # ---- 反射
    23920: ("反射", False),     # 法术反射 Spell Reflection
    # ---- 个人减伤
    48792: ("减伤", False),     # 冰封之韧 Icebound Fortitude
    49039: ("减伤", False),     # 巫妖之躯 Lichborne
    55233: ("减伤", False),     # 吸血鬼之血 Vampiric Blood
    198589: ("减伤", False),    # 疾影 Blur
    187827: ("减伤", False),    # 恶魔变形（复仇）
    22812: ("减伤", False),     # 树皮术 Barkskin
    61336: ("减伤", False),     # 生存本能 Survival Instincts
    108238: ("减伤", False),    # 甘霖 Renewal
    363916: ("减伤", False),    # 黑曜鳞片 Obsidian Scales
    374348: ("减伤", False),    # 新生光焰 Renewing Blaze
    109304: ("减伤", False),    # 意气风发 Exhilaration
    264735: ("减伤", False),    # 优胜劣汰 Survival of the Fittest
    342245: ("减伤", False),    # 操控时间 Alter Time
    235450: ("减伤", False),    # 棱光护盾 Prismatic Barrier
    235313: ("减伤", False),    # 烈焰护体 Blazing Barrier
    11426: ("减伤", False),     # 寒冰护体 Ice Barrier
    55342: ("减伤", False),     # 镜像 Mirror Image
    110960: ("减伤", False),    # 强化隐形术 Greater Invisibility（隐形期间及之后 3 秒减伤 60%，不解减益）
    414658: ("减伤", False),    # 深寒凝冰 Ice Cold（替代寒冰屏障：只减伤、不免疫）
    115203: ("减伤", False),    # 壮胆酒 Fortifying Brew（12.x 散魔功变被动：开壮胆酒时把魔法效果反弹给施法者）
    122470: ("减伤", False),    # 业报之触 Touch of Karma
    122783: ("自解", False),    # 散魔功 Diffuse Magic（旧版主动）
    122278: ("减伤", False),    # 躯不坏 Dampen Harm
    498: ("减伤", False),       # 圣佑术 Divine Protection
    403876: ("减伤", False),    # 圣佑术（惩戒）
    184662: ("减伤", False),    # 复仇之盾 Shield of Vengeance
    31850: ("减伤", False),     # 炽热防御者 Ardent Defender
    86659: ("减伤", False),     # 远古列王守卫 Guardian of Ancient Kings
    19236: ("减伤", False),     # 绝望祷言 Desperate Prayer
    586: ("减伤", False),       # 渐隐术 Fade
    5277: ("减伤", False),      # 闪避 Evasion
    185311: ("减伤", False),    # 猩红之瓶 Crimson Vial
    1966: ("减伤", False),      # 佯攻 Feint
    108271: ("减伤", False),    # 星界转移 Astral Shift
    104773: ("减伤", False),    # 不灭决心 Unending Resolve
    108416: ("减伤", False),    # 黑暗契约 Dark Pact
    118038: ("减伤", False),    # 剑在人在 Die by the Sword
    184364: ("减伤", False),    # 狂怒回复 Enraged Regeneration
    871: ("减伤", False),       # 盾墙 Shield Wall
    12975: ("减伤", False),     # 破釜沉舟 Last Stand
    202168: ("减伤", False),    # 胜利在望 Impending Victory
    # ---- 外部减伤
    6940: ("外部减伤", False),  # 牺牲祝福 Blessing of Sacrifice
    33206: ("外部减伤", False), # 痛苦压制 Pain Suppression
    47788: ("外部减伤", False), # 守护之魂 Guardian Spirit
    102342: ("外部减伤", False),# 铁木树皮 Ironbark
    116849: ("外部减伤", False),# 作茧缚命 Life Cocoon
    357170: ("外部减伤", False),# 时间膨胀 Time Dilation
    3411: ("外部减伤", False),  # 援护 Intervene
    633: ("外部减伤", False),   # 圣疗术 Lay on Hands
    # ---- 团队减伤
    51052: ("团队减伤", True),  # 反魔法领域 Anti-Magic Zone
    196718: ("团队减伤", True), # 黑暗 Darkness
    31821: ("团队减伤", True),  # 光环掌握 Aura Mastery
    62618: ("团队减伤", True),  # 真言术：障 Power Word: Barrier
    98008: ("团队减伤", True),  # 灵魂链接图腾 Spirit Link Totem
    97462: ("团队减伤", True),  # 集结呐喊 Rallying Cry
    374227: ("团队减伤", True), # 微风 Zephyr
    363534: ("团队减伤", True), # 回溯 Rewind
    15286: ("团队减伤", True),  # 吸血鬼的拥抱 Vampiric Embrace
    # ---- 解控
    1044: ("解控", False),      # 自由祝福 Blessing of Freedom
    116841: ("解控", False),    # 迅如猛虎 Tiger's Lust
    192077: ("解控", True),     # 狂风图腾 Wind Rush Totem
    8143: ("解控", True),       # 战栗图腾 Tremor Totem
    48265: ("解控", False),     # 死亡脚步 Death's Advance
    212552: ("解控", False),    # 幽魂步 Wraith Walk
    18499: ("解控", False),     # 狂暴之怒 Berserker Rage
    384100: ("解控", False),    # 狂暴护盾 Berserker Shout
    53271: ("解控", False),     # 主人的召唤 Master's Call
    272682: ("解控", False),    # 主人的召唤（命令宠物）
    198793: ("解控", False),    # 复仇回避 Vengeful Retreat（移除减速）
    370665: ("解控", False),    # 营救 Rescue（清除自己和队友的移动限制）
    357210: ("解控", False),    # 深呼吸 Deep Breath（移除定身，飞行中免控）
    359816: ("解控", False),    # 梦境飞行 Dream Flight
    403631: ("解控", False),    # 亘古吐息 Breath of Eons
    768: ("解控", False),       # 猎豹形态（变形解除定身/减速）
    5487: ("解控", False),      # 熊形态
    783: ("解控", False),       # 旅行形态
    24858: ("解控", False),     # 枭兽形态
    58875: ("解控", False),     # 幽魂之狼 Spirit Walk
    77761: ("位移", True),      # 狂奔怒吼 Stampeding Roar（12.x 只加速）
    106898: ("位移", True),     # 狂奔怒吼
    73325: ("位移", False),     # 信仰飞跃 Leap of Faith（把队友拉过来）
    # ---- 位移
    1953: ("位移", False), 212653: ("位移", False), 781: ("位移", False), 186257: ("位移", False),
    195072: ("位移", False), 189110: ("位移", False), 109132: ("位移", False), 115008: ("位移", False),
    358267: ("位移", False), 2983: ("位移", False), 36554: ("位移", False), 6544: ("位移", False),
    48020: ("位移", False), 111771: ("位移", False), 190784: ("位移", False), 102401: ("位移", False),
    252216: ("位移", False), 1850: ("位移", False), 121536: ("位移", False), 79206: ("位移", False),
    # ---- 控制
    408: ("控制", True), 179057: ("控制", True), 207684: ("控制", True), 202137: ("控制", True),
    202138: ("控制", True), 99: ("控制", True), 132469: ("控制", True), 102793: ("控制", True),
    109248: ("控制", True), 186387: ("控制", True), 236776: ("控制", True), 31661: ("控制", True),
    157981: ("控制", True), 113724: ("控制", True), 119381: ("控制", True), 116844: ("控制", True),
    115750: ("控制", True), 853: ("控制", False), 8122: ("控制", True), 205364: ("控制", False),
    51490: ("控制", True), 192058: ("控制", True), 30283: ("控制", True), 5246: ("控制", True),
    46968: ("控制", True), 107570: ("控制", False), 368970: ("控制", True), 357214: ("控制", True),
    221562: ("控制", False), 207167: ("控制", True), 49576: ("控制", False), 108199: ("控制", True),
    2094: ("控制", False), 1776: ("控制", False), 6789: ("控制", False), 5484: ("控制", True),
    # ---- 消耗品
    6262: ("消耗品", False), 452930: ("消耗品", False),
    # ---- 团队增益（战斗中补 buff，不是应对机制）
    1459: ("增益", True), 6673: ("增益", True), 21562: ("增益", True), 1126: ("增益", True),
    364342: ("增益", True), 462854: ("增益", True), 381748: ("增益", True),
    # ---- 战复
    20484: ("战复", False), 61999: ("战复", False), 20707: ("战复", False), 391054: ("战复", False),
}

NAME_HINTS = {
    "治疗石": "消耗品", "Healthstone": "消耗品", "药水": "消耗品", "Potion": "消耗品",
}

for _gid in KICK_SPELLS:
    SPELLS.setdefault(_gid, ("打断", False))


def category(gid: int, name: Optional[str] = None) -> Optional[str]:
    hit = SPELLS.get(int(gid))
    if hit:
        return hit[0]
    if name:
        for hint, cat in NAME_HINTS.items():
            if hint in name:
                return cat
    return None


def is_group(gid: int) -> bool:
    hit = SPELLS.get(int(gid))
    return bool(hit and hit[1])
