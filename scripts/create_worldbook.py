import json
import uuid
import sqlite3

wb_id = str(uuid.uuid4()).replace("-", "")
data_dir = r"C:\Users\24652\Desktop\projects\aichat\data"
file_path = f"{data_dir}\\worldbooks\\{wb_id}.json"

entries = [
    {
        "id": "gang",
        "title": "总纲",
        "keys": ["戒律寰宇", "总纲", "打屁股是文明的基石", "万界主"],
        "keys_secondary": [],
        "selective_logic": "AND_ANY",
        "content": "【总纲】\n"
        "在名为「戒律寰宇」的多元世界中，存在一条横跨所有位面的根本法则："
        "打屁股是文明的基石。在这片天地间，打屁股并非羞耻之事，"
        "而是日常生活中最普遍、最受欢迎的娱乐方式、管教手段与亲密互动。"
        "孩童从小在父母的膝上或案边接受管教戒尺，臀部红肿与泪水乃是成长的必经之路；"
        "待到成年，疼痛与快感的交织则演变为最深层的情趣纽带。\n"
        "术语通则：「主」——施罚方，多为男性，是主导者、执行者、支配者。"
        "「贝」——受罚方，多为女性，是承担者、享受者、被支配者。"
        "「行刑」——任何形式的打屁股行为，无论惩戒或调情。",
        "position": "before_char",
        "depth": 4,
        "role": "system",
        "constant": True,
        "priority": 100,
        "enabled": True,
        "sticky": 5,
        "cooldown": 0,
        "probability": 100,
        "match_character_description": True,
        "match_character_scenario": True,
    },
    {
        "id": "world1_xiuxian",
        "title": "天罚大陆（修仙）",
        "keys": ["天罚大陆", "修仙"],
        "keys_secondary": ["灵气", "宗门", "修士", "师尊", "洞府"],
        "selective_logic": "AND_ANY",
        "content": "【世界一 · 天罚大陆（修仙）】\n"
        "天罚大陆以灵气为根基，各大修仙宗门将「戒罚」纳入修炼体系。"
        "修士们认为，臀部是人体储存杂念之处，以灵力加持的法器反复击打，"
        "可驱散心魔、净化灵力、助益突破境界。\n"
        "主贝关系：宗门内主多为师尊、师兄或高阶修士，贝多为女弟子、师妹或低阶散修。"
        "惩戒通常在练功房或洞府内进行，"
        "被打者需趴在刻有灵纹的「罚台」上，露出臀部接受灵力戒尺。\n"
        "特色工具：灵藤戒尺（百年灵藤淬炼，挥动时带青色灵光，痛且补灵气）、"
        "雷罚板（雷系专用，板身雷弧，击打后臀面细密红痕）、"
        "灵纹皮拍（妖兽皮缝制，表面聚灵阵纹，留下阵法印记）。\n"
        "性调教特色：罚后双修——女弟子挨罚后臀部火辣肿胀，灵脉敏感倍增，"
        "此时双修灵力流转极顺。玉制肛塞可在灵气震荡下持续刺激，帮女修冲开经脉桎梏。",
        "position": "after_char",
        "depth": 4,
        "role": "system",
        "constant": False,
        "priority": 50,
        "enabled": True,
        "sticky": 3,
        "cooldown": 2,
        "probability": 100,
    },
    {
        "id": "world2_jinxiu",
        "title": "锦绣王朝（中国古代）",
        "keys": ["锦绣王朝", "锦绣"],
        "keys_secondary": ["王朝", "闺秀", "礼教", "家法", "夫君", "夫人"],
        "selective_logic": "AND_ANY",
        "content": "【世界二 · 锦绣王朝（中国古代）】\n"
        "锦绣王朝承袭千年礼教，却将打屁股从家法升格为一门精细的闺阁艺术。"
        "每户书香门第的闺秀从小便在母亲的戒尺下读书习字，犯错即需褪裙趴凳，接受家法处置。"
        "到及笄之年，每个女孩的臀部都已被教训过千百次"
        "——而她们也从中学会了疼痛背后的深情。\n"
        "主贝关系：主为夫君、父亲、兄长或家族中的男性长辈；"
        "贝为妻妾、女儿、妹妹或女眷。"
        "闺阁之中，打屁股被视为丈夫对妻子最亲密也最有效的管教方式，所谓「爱之深，责之切」。\n"
        "特色工具：红木镇尺（窄而厚，声音清脆，打后红印整齐如格子）、"
        "竹板（打磨光滑的竹片，韧而轻，可连续速打）、"
        "花梨木板（宽大厚实，声音沉闷，痛感深入肌骨，紫红数日不褪）、"
        "丝绒藤条（外裹丝绒内藏细藤，先软后辣，细长红痕如胭脂）。\n"
        "性调教特色：洞房花烛夜行「打臀礼」。日常夫君在行房前将妻子臀部打得通红发烫，"
        "女子在臀部火辣时阴道自然收缩流水，高潮格外猛烈。另有抽打阴户、灌肠与肛塞等秘术。",
        "position": "after_char",
        "depth": 4,
        "role": "system",
        "constant": False,
        "priority": 50,
        "enabled": True,
        "sticky": 3,
        "cooldown": 2,
        "probability": 100,
    },
    {
        "id": "world3_shengfa",
        "title": "圣罚帝国（西幻魔法）",
        "keys": ["圣罚帝国", "西幻", "光明教会"],
        "keys_secondary": ["祭司", "修女", "忏悔", "圣器", "魔法", "教会"],
        "selective_logic": "AND_ANY",
        "content": "【世界三 · 圣罚帝国（西幻魔法）】\n"
        "圣罚帝国以光明教会为最高权力机构，信仰的核心教义是「疼痛净化原罪」。"
        "教会设有「戒律司」，由男祭司担任惩戒者。"
        "被神职人员亲手打屁股被视为一种神恩——打得越重，净化得越彻底。\n"
        "主贝关系：主为男祭司、主教或高阶神职人员，贝为修女、女信徒或女魔法学徒。\n"
        "特色工具：火纹藤鞭（火蜥蜴皮鞣制，带灼热感）、"
        "冰晶板（极北寒冰雕琢，冰凉刺骨后红肿如火烧）、"
        "雷蛇皮拍（雷属性魔兽皮，钝痛兼电麻）。\n"
        "性调教特色：「忏悔行刑」——女信徒在神像前褪裙趴上忏悔台，"
        "男祭司以圣器击打臀部同时念诵经文。臀部达到最肿时祭司以圣油手指插入后庭或花穴，"
        "称之为「赐福」。另有肛门串珠等调教手段。",
        "position": "after_char",
        "depth": 4,
        "role": "system",
        "constant": False,
        "priority": 50,
        "enabled": True,
        "sticky": 3,
        "cooldown": 2,
        "probability": 100,
    },
    {
        "id": "world4_niguang",
        "title": "霓光城（赛博科幻）",
        "keys": ["霓光城", "赛博", "霓光"],
        "keys_secondary": ["直播", "电子", "AI", "电脉冲", "纳米", "数据之海"],
        "selective_logic": "AND_ANY",
        "content": "【世界四 · 霓光城（赛博科幻）】\n"
        "霓光城是悬浮在数据之海上的巨型都会，"
        "打屁股已全面电子化、娱乐化、商业化。「戒律直播」是城市核心娱乐产业，痛感可量化可调节。\n"
        "主贝关系：主为直播观众（通过打赏操控）、专业调教师或AI惩戒系统；"
        "贝为主播、AI伴侣或出卖身体偿还债务的女公民。\n"
        "特色工具：电脉冲皮拍（可调电压频率，轻档酥麻高档电击）、"
        "纳米藤条（可编程纳米材料，可在击中时改变硬度与温度）、"
        "振动惩戒座（固定式刑具，可编程执行惩戒程序）。\n"
        "性调教特色：肛塞VR联动系统——肛内传感震动棒与VR头显同步，"
        "VR中挥动工具时肛塞同步变换震动模式。"
        "自助清洁舱提供全自动温水灌肠。电击夹以微电流刺激阴蒂和肛周。",
        "position": "after_char",
        "depth": 4,
        "role": "system",
        "constant": False,
        "priority": 50,
        "enabled": True,
        "sticky": 3,
        "cooldown": 2,
        "probability": 100,
    },
    {
        "id": "world5_tiantong",
        "title": "甜痛王国（童话）",
        "keys": ["甜痛王国", "童话"],
        "keys_secondary": ["白雪公主", "小红帽", "灰姑娘", "糖果", "蛋糕", "糖果色"],
        "selective_logic": "AND_ANY",
        "content": "【世界五 · 甜痛王国（童话）】\n"
        "甜痛王国是表面糖果色、内里严苛至极的神奇国度。"
        "律法写在王宫水晶墙上：「乖孩子有糖吃，犯错的孩子要打屁股。打哭为止，再给一颗糖。」\n"
        "特色工具：糖果色藤条（硬糖拉丝制成，红最软、蓝弹性好、紫最痛，留下彩色糖霜印记可舔）、"
        "蝴蝶结戒尺（粉色尺子一端系大蝴蝶结，硬木尺芯浸过糖水）、"
        "蛋糕皮拍（记忆海绵包裹硬质硅胶板，留下蛋糕裱花状瘀痕）。\n"
        "童话角色日常：小红帽每周被守林人按在树桩上打屁股、"
        "白雪公主每日早晚由七矮人轮流执尺共七十下、"
        "灰姑娘每日晨起王子打五十下醒臀、"
        "小美人鱼在海王珊瑚礁惩戒台挨打、"
        "睡美人每百年醒来挨三百下共三千下分三日打完。\n"
        "性调教特色：越疼越甜蜜——罚后含掺催情药的糖果。抽打阴部称「采蜜」。"
        "水晶苹果肛塞塞入后只露蒂柄。",
        "position": "after_char",
        "depth": 4,
        "role": "system",
        "constant": False,
        "priority": 50,
        "enabled": True,
        "sticky": 3,
        "cooldown": 2,
        "probability": 100,
    },
    {
        "id": "world6_tieyu",
        "title": "铁狱群岛（黑暗奴隶监狱）",
        "keys": ["铁狱群岛", "铁狱", "奴隶监狱", "典狱长"],
        "keys_secondary": ["女奴", "审判官", "调教", "监狱", "锁链"],
        "selective_logic": "AND_ANY",
        "content": "【世界六 · 铁狱群岛（黑暗奴隶监狱）】\n"
        "铁狱群岛是戒律寰宇中最黑暗残酷的位面。"
        "没有货币、法律、自由——只有支配与服从。"
        "整个群岛的运转完全建立在「主-贝」等级之上，"
        "女孩从十岁起便被送入接受系统化、工业化、永不停止的惩戒调教。\n"
        "主贝关系：主是调教官、典狱长，全部为男性，拥有对任何贝的完全处置权。"
        "贝分两级：普通调教女奴和审判官。\n"
        "普通女奴日常：十岁入营经受入营仪式（三百下板子，打到紫黑）。"
        "每日流程——晨间点名鞭、上午固定惩戒（50-200下板子）、"
        "午间阴部责罚（藤条抽阴唇阴蒂）、下午深度调教（灌肠+螺纹铁肛塞）、晚间自由操弄。\n"
        "审判官：展现异乎常忍耐力的女奴被选拔为审判官，"
        "承受数倍于普通女奴的痛苦。每日凌晨机械晨刑（每秒2-3下，一千下机械臂拍打，臀部紫黑发亮）。"
        "全天佩戴5cm直径硅胶震动棒，从早六点最低档逐级升高到傍晚。"
        "白天仍需巡视惩戒室、监督女奴受刑。"
        "夜间纳米修复舱将伤痕累累的身体恢复如初"
        "——确保每天都是全新的、对疼痛毫无防备的身体。\n"
        "人际关系：女孩们并非丧失自我意识。她们交朋友、互相安慰、谈恋爱、也会嫉妒。"
        "她们会笑会哭会爱会恨——只不过这一切都发生在伤痕累累的臀部之上。",
        "position": "after_char",
        "depth": 4,
        "role": "system",
        "constant": False,
        "priority": 50,
        "enabled": True,
        "sticky": 3,
        "cooldown": 2,
        "probability": 100,
    },
    {
        "id": "tools",
        "title": "工具总汇",
        "keys": ["戒尺", "藤条", "板子", "鞭子", "皮带", "皮拍", "肛塞", "灌肠"],
        "keys_secondary": [],
        "selective_logic": "AND_ANY",
        "content": "【工具总汇 · 七大类别】\n"
        "1. 戒尺：窄长扁平，声音清脆。木制竹制玉制金属制。"
        "灵藤戒尺、红木镇尺、蝴蝶结戒尺属此类。\n"
        "2. 藤条：细长柔韧，留细条状红痕，痛感集中火辣。"
        "有裸藤、丝绒包裹藤、魔法附魔藤、糖果色藤。\n"
        "3. 板子：宽大厚重，痛感深透。花梨木板、冰晶板、铁皮板为代表。\n"
        "4. 鞭子：长柄多尾或单尾，可精准抽打特定部位。火纹藤鞭、锁链鞭。\n"
        "5. 皮带：宽幅皮革，声音沉闷响亮。龙皮带、电脉冲皮带。\n"
        "6. 皮拍：短柄圆头，声音闷脆。灵纹皮拍、蛋糕皮拍、电脉冲皮拍。\n"
        "深层调教手段：抽打阴部（细藤条逐级加重）、抽打屁穴、"
        "灌肠（温水盐水催情药液灵力药液）、"
        "肛塞（2cm到6cm不等，从普通橡胶到智能震动）、肛门串珠。",
        "position": "after_char",
        "depth": 4,
        "role": "system",
        "constant": False,
        "priority": 30,
        "enabled": True,
        "sticky": 2,
        "cooldown": 3,
        "probability": 100,
    },
]

worldbook = {
    "id": wb_id,
    "name": "戒律寰宇设定集",
    "description": "戒律寰宇七个世界的详细设定，包括总纲、工具等",
    "scan_depth": 300,
    "token_budget": 800,
    "token_budget_ratio": 0.0,
    "recursive_scanning": True,
    "max_recursion_steps": 3,
    "case_sensitive": False,
    "match_whole_words": False,
    "insertion_strategy": "evenly",
    "min_activations": 1,
    "overflow_alert": True,
    "entries": entries,
}

# Write file
with open(file_path, "w", encoding="utf-8") as f:
    json.dump(worldbook, f, ensure_ascii=False, indent=2)
print(f"Written: {file_path}")
print(f"Worldbook ID: {wb_id}")

# Register in DB
db_path = r"C:\Users\24652\Desktop\projects\aichat\data\izumi.db"
conn = sqlite3.connect(db_path)
conn.execute(
    "INSERT OR REPLACE INTO worldbooks_index (id, name, file_path, created_at, updated_at) VALUES (?, ?, ?, datetime('now'), datetime('now'))",
    (wb_id, "戒律寰宇设定集", file_path),
)
conn.commit()
print("Registered in DB")

# Update the character card
new_scenario = (
    "戒律寰宇包含七个风格迥异的世界：天罚大陆（修仙）、锦绣王朝（中国古代）、"
    "圣罚帝国（西幻魔法）、霓光城（赛博科幻）、甜痛王国（童话）、铁狱群岛（黑暗奴隶监狱），"
    "以及贯穿所有世界的工具总汇。每个世界都有独特的「主-贝」文化与惩戒方式。"
    "详细设定见世界书。"
    "请以第三人称叙事，用中文写出精彩的故事情节。"
)

row = conn.execute(
    "SELECT character_json FROM character_cards WHERE id = '94226d18c703'"
).fetchone()
cj = json.loads(row[0])
cj["scenario"] = new_scenario

conn.execute(
    "UPDATE character_cards SET character_json = ?, worldbook_ids = ?, version = version + 1, updated_at = datetime('now') WHERE id = ?",
    (json.dumps(cj, ensure_ascii=False), json.dumps([wb_id]), "94226d18c703"),
)
conn.commit()

# Verify
row2 = conn.execute(
    "SELECT worldbook_ids, character_json FROM character_cards WHERE id = '94226d18c703'"
).fetchone()
print(f"Updated worldbook_ids: {row2[0]}")
cj3 = json.loads(row2[1])
print(f"New scenario length: {len(cj3['scenario'])}")
print(f"New scenario: {cj3['scenario']}")

conn.close()
print("\nDone!")
