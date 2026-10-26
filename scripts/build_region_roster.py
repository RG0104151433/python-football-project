"""Export the adopted team/date partition roster; no match outcomes are read."""
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "outputs/logs/regions/grouping-acceptance-20261026/preparation-20261026T090739Z-82cd5e84-accepted-r1"
OUT = ROOT / "outputs/tables/regions/preparation/regions-study-v2"
NAMES = """
benin:贝宁|burkina-faso:布基纳法索|cape-verde:佛得角|gambia:冈比亚|ghana:加纳|guinea:几内亚|guinea-bissau:几内亚比绍|ivory-coast:科特迪瓦|liberia:利比里亚|mali:马里|mauritania:毛里塔尼亚|niger:尼日尔|nigeria:尼日利亚|senegal:塞内加尔|sierra-leone:塞拉利昂|togo:多哥
burundi:布隆迪|comoros:科摩罗|djibouti:吉布提|eritrea:厄立特里亚|ethiopia:埃塞俄比亚|kenya:肯尼亚|madagascar:马达加斯加|malawi:马拉维|mauritius:毛里求斯|mozambique:莫桑比克|rwanda:卢旺达|seychelles:塞舌尔|somalia:索马里|south-sudan:南苏丹|tanzania:坦桑尼亚|uganda:乌干达|zambia:赞比亚|zimbabwe:津巴布韦
algeria:阿尔及利亚|egypt:埃及|libya:利比亚|morocco:摩洛哥|sudan:苏丹|tunisia:突尼斯
angola:安哥拉|cameroon:喀麦隆|central-african-republic:中非共和国|chad:乍得|congo:刚果共和国|dr-congo:刚果民主共和国|equatorial-guinea:赤道几内亚|gabon:加蓬|sao-tome-and-principe:圣多美和普林西比
botswana:博茨瓦纳|eswatini:埃斯瓦蒂尼|lesotho:莱索托|namibia:纳米比亚|south-africa:南非
australia:澳大利亚|new-zealand:新西兰|fiji:斐济|new-caledonia:新喀里多尼亚|papua-new-guinea:巴布亚新几内亚|solomon-islands:所罗门群岛|vanuatu:瓦努阿图|guam:关岛|american-samoa:美属萨摩亚|cook-islands:库克群岛|samoa:萨摩亚|tahiti:大溪地|tonga:汤加
argentina:阿根廷|bolivia:玻利维亚|brazil:巴西|chile:智利|colombia:哥伦比亚|ecuador:厄瓜多尔|guyana:圭亚那|paraguay:巴拉圭|peru:秘鲁|suriname:苏里南|uruguay:乌拉圭|venezuela:委内瑞拉
belize:伯利兹|costa-rica:哥斯达黎加|el-salvador:萨尔瓦多|guatemala:危地马拉|honduras:洪都拉斯|mexico:墨西哥|nicaragua:尼加拉瓜|panama:巴拿马|bermuda:百慕大|canada:加拿大|united-states:美国
anguilla:安圭拉|antigua-and-barbuda:安提瓜和巴布达|aruba:阿鲁巴|bahamas:巴哈马|barbados:巴巴多斯|british-virgin-islands:英属维尔京群岛|cayman-islands:开曼群岛|cuba:古巴|curacao:库拉索|dominica:多米尼克|dominican-republic:多米尼加共和国|grenada:格林纳达|haiti:海地|jamaica:牙买加|montserrat:蒙特塞拉特|puerto-rico:波多黎各|saint-kitts-and-nevis:圣基茨和尼维斯|saint-lucia:圣卢西亚|saint-vincent-and-the-grenadines:圣文森特和格林纳丁斯|sint-maarten:荷属圣马丁|trinidad-and-tobago:特立尼达和多巴哥|turks-and-caicos-islands:特克斯和凯科斯群岛|united-states-virgin-islands:美属维尔京群岛
china:中国|hong-kong:中国香港|japan:日本|macau:中国澳门|mongolia:蒙古|north-korea:朝鲜|south-korea:韩国|taiwan:中华台北
afghanistan:阿富汗|bangladesh:孟加拉国|bhutan:不丹|india:印度|iran:伊朗|maldives:马尔代夫|nepal:尼泊尔|pakistan:巴基斯坦|sri-lanka:斯里兰卡
brunei:文莱|cambodia:柬埔寨|indonesia:印度尼西亚|laos:老挝|malaysia:马来西亚|myanmar:缅甸|philippines:菲律宾|singapore:新加坡|thailand:泰国|timor-leste:东帝汶|vietnam:越南
kazakhstan:哈萨克斯坦|kyrgyzstan:吉尔吉斯斯坦|tajikistan:塔吉克斯坦|turkmenistan:土库曼斯坦|uzbekistan:乌兹别克斯坦
armenia:亚美尼亚|azerbaijan:阿塞拜疆|bahrain:巴林|cyprus:塞浦路斯|georgia:格鲁吉亚|iraq:伊拉克|israel:以色列|jordan:约旦|kuwait:科威特|lebanon:黎巴嫩|oman:阿曼|palestine:巴勒斯坦|qatar:卡塔尔|saudi-arabia:沙特阿拉伯|syria:叙利亚|turkey:土耳其|united-arab-emirates:阿联酋|yemen:也门
albania:阿尔巴尼亚|andorra:安道尔|bosnia-and-herzegovina:波斯尼亚和黑塞哥维那|croatia:克罗地亚|gibraltar:直布罗陀|greece:希腊|italy:意大利|kosovo:科索沃|malta:马耳他|montenegro:黑山|north-macedonia:北马其顿|portugal:葡萄牙|san-marino:圣马力诺|serbia:塞尔维亚|slovenia:斯洛文尼亚|spain:西班牙|yugoslavia:南斯拉夫
belarus:白俄罗斯|bulgaria:保加利亚|czech-republic:捷克|czechoslovakia:捷克斯洛伐克|hungary:匈牙利|moldova:摩尔多瓦|poland:波兰|romania:罗马尼亚|russia:俄罗斯|slovakia:斯洛伐克|ukraine:乌克兰
denmark:丹麦|england:英格兰|estonia:爱沙尼亚|faroe-islands:法罗群岛|finland:芬兰|iceland:冰岛|latvia:拉脱维亚|lithuania:立陶宛|northern-ireland:北爱尔兰|norway:挪威|republic-of-ireland:爱尔兰|scotland:苏格兰|sweden:瑞典|wales:威尔士
austria:奥地利|belgium:比利时|france:法国|german-dr:民主德国（东德）|germany:德国|liechtenstein:列支敦士登|luxembourg:卢森堡|netherlands:荷兰|switzerland:瑞士
"""
ZH = {"team:"+part.split(":",1)[0]:part.split(":",1)[1] for part in NAMES.replace("\n","|").split("|") if part}
REGIONS = {"002":"非洲","019":"美洲","142":"亚洲","150":"欧洲","009":"大洋洲"}
UNITS = {"011":"西非","014":"东非","015":"北非","017":"中部非洲","018":"南部非洲",
         "005":"南美洲","013":"中美洲","021":"北部美洲","029":"加勒比地区",
         "030":"东亚","034":"南亚","035":"东南亚","143":"中亚","145":"西亚",
         "039":"南欧","151":"东欧","154":"北欧","155":"西欧",
         "053":"澳大利亚和新西兰","054":"美拉尼西亚","057":"密克罗尼西亚","061":"波利尼西亚"}


def read(path):
    with path.open(encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))


def main():
    names={r["team_id"]:r["current_label"] for r in read(RUN/"team_inventory.csv")}
    assert set(names)==set(ZH), (set(names)-set(ZH),set(ZH)-set(names))
    rules=read(RUN/"team_geography_rules.csv")
    matches=read(RUN/"match_region_relations.csv")
    counts={role:Counter(r[role+"_rule_id"] for r in matches) for role in ["home","away"]}
    output=[]
    groups=defaultdict(list)
    for r in rules:
        tid,reg,unit=r["team_id"],r["project_region_code"],r["project_unit_code"]
        row=dict(protocol_id="regions-study-v2",rule_id=r["rule_id"],team_id=tid,
                 team_name_zh=ZH[tid],source_team_label=names[tid],region_code=reg,
                 region_name=REGIONS.get(reg,"未定"),partition_code=unit,
                 partition_name=UNITS.get(unit,"未定"),date_start=r["date_start"],date_end=r["date_end"],
                 carrier_m49_code=r["carrier_m49_code"],classification_basis=r["status"],
                 home_matches=counts["home"][r["rule_id"]],away_matches=counts["away"][r["rule_id"]],
                 note="固定现代载体，不表示历史官方区划" if r["carrier_kind"]=="historical_association_carrier" else r["reason"])
        output.append(row)
        if unit:
            groups[reg,unit].append(dict(team_id=tid,name_zh=ZH[tid],source_label=names[tid]))
    assert len(output)==217 and len(groups)==22
    assert sum(r["home_matches"] for r in output)==sum(r["away_matches"] for r in output)==24917
    OUT.mkdir(parents=True,exist_ok=True)
    with (OUT/"team_geography_roster.csv").open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(output[0]),lineterminator="\n")
        w.writeheader();w.writerows(sorted(output,key=lambda r:(r["region_code"],r["partition_code"],r["team_id"],r["date_start"])))
    data={"protocol_id":"regions-study-v2","scope":"Actual study teams, not all sovereign states or all M49 areas",
          "teams":215,"date_rules":217,"partitions":[],"unknown_date_rules":2,
          "chinese_names":"Project display labels; original labels and IDs retained"}
    for (reg,unit),teams in sorted(groups.items()):
        data["partitions"].append(dict(region_code=reg,region=REGIONS[reg],partition_code=unit,
                                       partition=UNITS[unit],teams=teams))
    (OUT/"partition_teams.json").write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8",newline="\n")
    print(json.dumps({"teams":215,"rules":217,"partitions":22,"output":OUT.relative_to(ROOT).as_posix()},ensure_ascii=True))


if __name__=="__main__":
    main()
